import SwiftUI

/// Empty host app. macOS UI test bundles need a target application; the
/// agent drives VoiceOver, not this app.
@main
struct AgentHostApp: App {
  var body: some Scene {
    WindowGroup { Text("Guidepup VoiceOver agent host") }
  }
}
