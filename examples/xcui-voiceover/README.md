# XCUI VoiceOver

Reads a web page in Safari, element by element, using Apple's [`XCUIVoiceOverService`](https://developer.apple.com/documentation/xcuiautomation/xcuivoiceoverservice) (macOS 27). Each move returns what VoiceOver said directly, with no polling of VoiceOver over AppleScript.

Run this example with:

```bash
npx ts-node ./examples/xcui-voiceover/index.ts            # the bundled page.html
npx ts-node ./examples/xcui-voiceover/index.ts <url> [steps]
```

Output on macOS 27.0 with Safari 27.0:

```text
1 forward: link Skip to main content
2 forward: Primary navigation
...
12 forward: heading level 1 Hello from XCUIVoiceOverService
13 forward: Each step below is what VoiceOver said after one move.
14 forward: heading level 2 A deliberately long heading that runs past the s [truncated at 64 characters]
15 forward: Search
16 forward: search text field blank
17 forward: Add to cart button
18 forward: button
19 forward: end of main
...
21 forward: (VoiceOver said nothing)
22 forward: (VoiceOver said nothing)
23 forward: (VoiceOver said nothing)
The VoiceOver cursor stopped moving; end of the page.
```

Step 18 is the icon-only button in `page.html`: VoiceOver can only say "button", which is exactly the kind of unlabelled control this is useful for finding.

## Requirements

- macOS 27 and Xcode 27 (`xcode-select -s /Applications/Xcode.app`). Command Line Tools alone don't include XCTest.
- The usual [VoiceOver prerequisites](https://www.guidepup.dev/docs/guides/environment).
- Approve the UI automation prompt the first time. While the agent runs, macOS may show an "automation running" overlay; keyboard and mouse keep working.

## How it works

`XCUIDevice.shared.voiceOverService` only works inside an authorised UI test run. So `XcuiAgent` builds a small XCTest target ([`xcui-agent/`](../../xcui-agent)) and runs it as a long-lived "test" that takes commands. The build happens once and is cached in `~/Library/Caches/guidepup/xcui-agent`. Xcode's test runner is app-sandboxed and isn't allowed to listen on a port, so the agent connects back to a socket that `XcuiAgent` opens on `127.0.0.1`. It identifies itself with a random token, then answers newline-delimited JSON commands.

guidepup still starts and stops VoiceOver (`voiceOver.start()` / `voiceOver.stop()`). The agent never turns VoiceOver on or off.

## Caveats

- **Utterances are cut off at 64 characters** by `XCUIVoiceOverService` as of Xcode 27.0. Responses flag this with `truncated: true`.
- **Silence is reported, not thrown.** When VoiceOver says nothing for an element, `move()` returns `{ utterance: "", silent: true }`. That's often an unlabelled control worth investigating. Repeated silence or repeated speech means the cursor has stopped moving.
- `moveForward()` won't enter Safari's web area on its own. Use `move("in")` when the cursor lands on "web content".
- The service only offers forward, backward, in and out moves. Jumping by heading, using the rotor, and typing still go through guidepup's keyboard commands.
- `xcui-agent/` isn't included in the published npm package yet, so run this from a checkout.
