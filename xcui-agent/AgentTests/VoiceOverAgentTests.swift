import Network
import XCTest

/// Serves XCUIVoiceOverService over a local socket so guidepup can drive it.
///
/// XCUIDevice is only usable inside an authorised UI test run, so this test
/// stays running as a server until it is told to shut down. VoiceOver itself
/// must already be running: the agent never enables or disables it.
@MainActor
final class VoiceOverAgentTests: XCTestCase {
  func testServe() throws {
    let env = ProcessInfo.processInfo.environment
    let token = try XCTUnwrap(env["AGENT_TOKEN"], "AGENT_TOKEN is required")
    let port = try XCTUnwrap(NWEndpoint.Port(env["AGENT_PORT"] ?? ""), "AGENT_PORT is required")

    // The runner is app-sandboxed with only the network client entitlement,
    // so the agent connects out to guidepup rather than listening itself.
    let agent = Agent(port: port, token: token)
    agent.start()

    // XCUIVoiceOverService is main-actor bound, so keep the main run loop
    // turning (and the connection on the main queue) until shutdown.
    while !agent.isShutdown {
      RunLoop.main.run(mode: .default, before: Date(timeIntervalSinceNow: 0.1))
    }
  }
}

/// Protocol: newline-delimited JSON over a TCP connection to 127.0.0.1:<port>.
/// The agent first sends {"hello":"<token>"}, then answers one response line
/// per request line, e.g. {"command":"move","direction":"forward"} gets
/// {"ok":true,"utterance":"…","truncated":false}.
@MainActor
final class Agent {
  /// XCUIVoiceOverService.Output.utterance is cut off at this many characters.
  static let utteranceLimit = 64

  private(set) var isShutdown = false
  private let connection: NWConnection
  private let token: String

  init(port: NWEndpoint.Port, token: String) {
    connection = NWConnection(host: .ipv4(.loopback), port: port, using: .tcp)
    self.token = token
  }

  func start() {
    connection.stateUpdateHandler = { state in
      MainActor.assumeIsolated {
        print("AGENT connection \(state)")

        switch state {
        case .ready:
          self.send(["hello": self.token], on: self.connection)
        case .failed, .cancelled:
          self.isShutdown = true
        default:
          break
        }
      }
    }
    connection.start(queue: .main)
    receive(on: connection, buffer: Data())
  }

  private func receive(on connection: NWConnection, buffer: Data) {
    connection.receive(minimumIncompleteLength: 1, maximumLength: 65536) { data, _, isComplete, error in
      MainActor.assumeIsolated {
        var buffer = buffer
        if let data { buffer.append(data) }

        while let newline = buffer.firstIndex(of: UInt8(ascii: "\n")) {
          let line = buffer[buffer.startIndex..<newline]
          buffer = Data(buffer[buffer.index(after: newline)...])
          self.respond(to: line, on: connection)
        }

        if isComplete || error != nil {
          self.isShutdown = true
          connection.cancel()
        } else {
          self.receive(on: connection, buffer: buffer)
        }
      }
    }
  }

  private func respond(to line: Data, on connection: NWConnection) {
    let response = handle(line)

    // Close only once the shutdown reply has gone out.
    send(response, on: connection) { [isShutdown] in
      if isShutdown { connection.cancel() }
    }
  }

  private func send(
    _ message: [String: Any], on connection: NWConnection, then: @escaping @Sendable () -> Void = {}
  ) {
    var payload = (try? JSONSerialization.data(withJSONObject: message)) ?? Data(#"{"ok":false}"#.utf8)
    payload.append(UInt8(ascii: "\n"))
    connection.send(content: payload, completion: .contentProcessed { _ in then() })
  }

  private func handle(_ line: Data) -> [String: Any] {
    guard let request = try? JSONSerialization.jsonObject(with: line) as? [String: Any] else {
      return ["ok": false, "error": "malformed request"]
    }

    let voiceOver = XCUIDevice.shared.voiceOverService

    do {
      switch request["command"] as? String {
      case "status":
        return ["ok": true, "isEnabled": voiceOver.isEnabled]
      case "speech":
        return speech(try voiceOver.currentSpeech())
      case "move":
        switch request["direction"] as? String {
        case "forward": return speech(try voiceOver.moveForward())
        case "backward": return speech(try voiceOver.moveBackward())
        case "in": return speech(try voiceOver.moveIn())
        case "out": return speech(try voiceOver.moveOut())
        default: return ["ok": false, "error": "unknown direction"]
        }
      case "shutdown":
        isShutdown = true
        return ["ok": true]
      default:
        return ["ok": false, "error": "unknown command"]
      }
    } catch {
      let nsError = error as NSError
      return ["ok": false, "error": nsError.localizedDescription, "code": nsError.code, "domain": nsError.domain]
    }
  }

  private func speech(_ output: XCUIVoiceOverService.Output) -> [String: Any] {
    ["ok": true, "utterance": output.utterance, "truncated": output.utterance.count >= Self.utteranceLimit]
  }
}
