// awin's approval window: our own panel holding one web view (the page render.py builds, no script, nothing loaded)
// and two native buttons. argv: <html file> <window title> <approve button label> <page height> <tint hex or "">.
// The tint (style tag only) is a colored ring behind the approve button; it never makes it the default button.
// Prints "approved" only when the approve button is clicked; anything else (Cancelar, Escape, the close button, a
// failure) prints "cancelled". Cancelar has Escape; the approve button has no key equivalent, nothing is the
// window's default button, and the approve button refuses first responder, so Return, Enter and Space cannot press it
// (not even with Full Keyboard Access on); approving takes a click.
ObjC.import('Cocoa');
ObjC.import('WebKit');

let result = 'cancelled';
// Approve is enabled only once the page has loaded: a blank window must never be approvable (a person approved one,
// 2026-10-14). The load is asynchronous, so a navigation delegate decides; a failure reloads once, then only Cancelar
// is left. The web view holds its delegate weakly, so these globals keep it alive.
// Approve turns on APPROVE_DELAY seconds after the load finished, not at once, so a click already on its way when the
// window appears cannot approve. Only the loads awin starts (the page, and one reload) may navigate the web view: it
// accepts no drags (a dropped file would replace the page), and if any other navigation starts anyway the page is
// tainted and Approve never turns on again. (There is no navigation policy delegate: JXA cannot call the completion
// block WebKit passes it, and declaring that method kills osascript; measured 2026-10-23.)
const APPROVE_DELAY = 0.7;
let ok = null;
let page = null;
let pageView = null;
let pageDelegate = null;
let retries = 0;
let expectedLoads = 0;  // loads awin started that have not begun yet
let generation = 0;     // bumped by every navigation start and by a web process crash
let armed = -1;         // the generation the pending enable timer belongs to
let tainted = false;    // a navigation awin did not start began: Apruebo stays disabled
let enableTimer = null; // the pending enable, invalidated by any navigation start, crash or newer load

function cancelEnable() {
  if (enableTimer) {
    enableTimer.invalidate;
    enableTimer = null;
  }
}

function loadPage() {
  expectedLoads += 1;
  pageView.loadHTMLStringBaseURL(page, $.NSURL.URLWithString('about:blank'));
}

function reloadOnce(why) {
  if (retries < 1 && pageView && page && !tainted) {
    retries += 1;
    loadPage();
  } else {
    console.log('awin: the approval page did not load (' + why + '); Apruebo stays disabled');
  }
}

ObjC.registerSubclass({
  name: 'AwinPageDelegate',
  superclass: 'NSObject',
  protocols: ['WKNavigationDelegate', 'WKUIDelegate'],
  methods: {
    // A navigation that starts without awin having started it taints the page: Apruebo never turns on again.
    'webView:didStartProvisionalNavigation:': {
      types: ['void', ['id', 'id']],
      implementation: function (view, navigation) {
        cancelEnable();
        generation += 1;
        if (ok) { ok.enabled = false; }
        if (expectedLoads > 0) {
          expectedLoads -= 1;
        } else {
          tainted = true;
        }
      },
    },
    // The page has no links (every caller string is escaped text), so nothing opens; nil creates no new view.
    'webView:createWebViewWithConfiguration:forNavigationAction:windowFeatures:': {
      types: ['id', ['id', 'id', 'id', 'id']],
      implementation: function (view, configuration, action, features) {
        return $();
      },
    },
    // The timer runs in the common modes: runModalForWindow runs NSModalPanelRunLoopMode, where a default-mode
    // timer would never fire.
    'webView:didFinishNavigation:': {
      types: ['void', ['id', 'id']],
      implementation: function (view, navigation) {
        cancelEnable();
        if (!ok || tainted) { return; }
        armed = generation;
        enableTimer = $.NSTimer.timerWithTimeIntervalTargetSelectorUserInfoRepeats(APPROVE_DELAY, pageDelegate, 'enableApprove:', null, false);
        $.NSRunLoop.currentRunLoop.addTimerForMode(enableTimer, $.NSRunLoopCommonModes);
      },
    },
    // Fired by the timer: enables Approve only if nothing navigated, crashed or tainted the page since the load finished.
    'enableApprove:': {
      types: ['void', ['id']],
      implementation: function (timer) {
        enableTimer = null;
        if (ok && !tainted && armed === generation) { ok.enabled = true; }
      },
    },
    'webView:didFailNavigation:withError:': {
      types: ['void', ['id', 'id', 'id']],
      implementation: function (view, navigation, error) { reloadOnce('navigation failed'); },
    },
    'webView:didFailProvisionalNavigation:withError:': {
      types: ['void', ['id', 'id', 'id']],
      implementation: function (view, navigation, error) { reloadOnce('provisional navigation failed'); },
    },
    'webViewWebContentProcessDidTerminate:': {
      types: ['void', ['id']],
      implementation: function (view) {
        cancelEnable();
        generation += 1;  // a pending enable no longer applies
        if (ok) { ok.enabled = false; }
        reloadOnce('web content process ended');
      },
    },
  },
});

ObjC.registerSubclass({
  name: 'AwinApprovalHandler',
  superclass: 'NSObject',
  protocols: ['NSWindowDelegate'],
  methods: {
    'approve:': {
      types: ['void', ['id']],
      implementation: function (sender) { result = 'approved'; $.NSApplication.sharedApplication.stopModal; },
    },
    'cancel:': {
      types: ['void', ['id']],
      implementation: function (sender) { $.NSApplication.sharedApplication.stopModal; },
    },
    'windowWillClose:': {
      types: ['void', ['id']],
      implementation: function (note) { $.NSApplication.sharedApplication.stopModal; },
    },
  },
});

function run(argv) {
  const html = $.NSString.stringWithContentsOfFileEncodingError(argv[0], $.NSUTF8StringEncoding, null);
  if (!html || html.isNil()) {  // an unreadable page file never opens a window (JXA wraps nil, so !html alone is false)
    return 'cancelled';
  }
  const width = 460;
  const bar = 58;  // the button bar under the page
  const height = Number(argv[3]);

  const app = $.NSApplication.sharedApplication;
  app.setActivationPolicy($.NSApplicationActivationPolicyAccessory);
  app.activateIgnoringOtherApps(true);

  const handler = $.AwinApprovalHandler.alloc.init;
  const panel = $.NSPanel.alloc.initWithContentRectStyleMaskBackingDefer(
    $.NSMakeRect(0, 0, width, height + bar),
    $.NSWindowStyleMaskTitled | $.NSWindowStyleMaskClosable,
    $.NSBackingStoreBuffered,
    false);
  panel.title = argv[1];
  panel.level = $.NSFloatingWindowLevel;
  panel.delegate = handler;

  const config = $.WKWebViewConfiguration.alloc.init;
  config.defaultWebpagePreferences.allowsContentJavaScript = false;
  const web = $.WKWebView.alloc.initWithFrameConfiguration($.NSMakeRect(0, bar, width, height), config);
  web.unregisterDraggedTypes;  // a file dropped on the page would navigate away from it
  web.setValueForKey($.NSNumber.numberWithBool(false), 'drawsBackground');  // the window's own background shows through
  page = html;
  pageView = web;
  pageDelegate = $.AwinPageDelegate.alloc.init;
  web.navigationDelegate = pageDelegate;
  web.UIDelegate = pageDelegate;

  const cancel = $.NSButton.alloc.initWithFrame($.NSMakeRect(width - 24 - 130 - 10 - 90, 15, 90, 28));
  cancel.title = 'Cancelar';
  cancel.bezelStyle = $.NSBezelStyleRounded;
  cancel.target = handler;
  cancel.action = 'cancel:';
  cancel.keyEquivalent = '\u001b';

  ok = $.NSButton.alloc.initWithFrame($.NSMakeRect(width - 24 - 130, 15, 130, 28));
  ok.title = argv[2];
  ok.bezelStyle = $.NSBezelStyleRounded;
  ok.target = handler;
  ok.action = 'approve:';
  ok.keyEquivalent = '';
  ok.refusesFirstResponder = true;  // Tab cannot focus it, so Space cannot press it (Full Keyboard Access)
  ok.enabled = false;  // until APPROVE_DELAY after the page has loaded
  loadPage();

  panel.contentView.addSubview(web);
  panel.contentView.addSubview(cancel);
  const tint = argv[4] || '';
  if (/^#[0-9a-fA-F]{6}$/.test(tint)) {
    // A ring drawn behind Approve (an NSBox, so only NSColor crosses the JXA bridge; a Core Graphics color kills osascript).
    const rgb = [1, 3, 5].map(function (i) { return parseInt(tint.substr(i, 2), 16) / 255; });
    const ring = $.NSBox.alloc.initWithFrame($.NSMakeRect(width - 24 - 130 - 3, 15 - 3, 130 + 6, 28 + 6));
    ring.boxType = $.NSBoxCustom;
    ring.titlePosition = $.NSNoTitle;
    ring.borderColor = $.NSColor.colorWithSRGBRedGreenBlueAlpha(rgb[0], rgb[1], rgb[2], 1);
    ring.borderWidth = 2;
    ring.cornerRadius = 8;
    ring.fillColor = $.NSColor.clearColor;
    panel.contentView.addSubview(ring);  // before the button, so it draws behind it
  }
  panel.contentView.addSubview(ok);
  panel.center;
  panel.makeKeyAndOrderFront(null);
  $.NSBeep();  // once, for every level
  app.runModalForWindow(panel);
  panel.delegate = null;  // closing it below must not stop a modal session that is already over
  panel.orderOut(null);
  return result;
}
