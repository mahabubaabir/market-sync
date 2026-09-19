// Market Sync — Cinnamon panel applet (market-sync@cinnamon)
// Shows the live session countdowns from ~/.cache/market-sync/panel_status.json
// with bright/dim Pango markup. Left-click toggles the glass dropdown through
// the app's IPC (market-sync --toggle); right-click opens the applet menu.
//
// Design System v2.0 · Developed by Mahabub H. Aabir

const Applet = imports.ui.applet;
const GLib = imports.gi.GLib;
const Util = imports.misc.util;
const PopupMenu = imports.ui.popupMenu;

const UUID = "market-sync@cinnamon";
const STATUS_PATH = GLib.get_home_dir() + "/.cache/market-sync/panel_status.json";

// Optional fallback app directory (patched by install-applet.sh when run
// from a source checkout). Runtime detection below is tried first.
const PATCHED_APP_DIR = "__APP_DIR__";

function MarketSyncApplet(metadata, orientation, panel_height, instance_id) {
    this._init(metadata, orientation, panel_height, instance_id);
}

MarketSyncApplet.prototype = {
    __proto__: Applet.TextApplet.prototype,

    _init: function(metadata, orientation, panel_height, instance_id) {
        Applet.TextApplet.prototype._init.call(this, orientation, panel_height, instance_id);
        this.metadata = metadata;

        // Rich Pango markup for bright-open / dim-closed session chips
        if (this._applet_label && this._applet_label.clutter_text) {
            this._applet_label.clutter_text.set_use_markup(true);
        }

        this.set_applet_label("Market Sync");
        this.set_applet_tooltip("Market Sync — click to open the panel");

        // TextApplet has no icon actor, so the applet stays text-only.
        this._setup_context_menu();
        this._update();

        // 1-second refresh loop (reads the status file the app writes)
        this._timer_id = GLib.timeout_add_seconds(GLib.PRIORITY_DEFAULT, 1, () => {
            this._update();
            return true;
        });
    },

    _resolve_app_dir: function() {
        // Prefer an installed binary; fall back to python3 + main.py.
        let candidates = [
            PATCHED_APP_DIR,
            "/opt/market-sync",
            GLib.get_home_dir() + "/.local/share/market-sync",
        ];
        for (let dir of candidates) {
            if (dir && dir.indexOf("__APP_DIR__") === -1 &&
                GLib.file_test(dir + "/main.py", GLib.FileTest.EXISTS)) {
                return dir;
            }
        }
        return "";
    },

    _send_cmd: function(arg) {
        // IPC path: the applet asks the running daemon (or a fresh instance)
        // to toggle/show/prefs/quit through the same entry as the tray icon.
        let bin = GLib.find_program_in_path("market-sync");
        if (bin) {
            Util.spawnCommandLine('"' + bin + '" ' + arg);
            return;
        }
        let dir = this._resolve_app_dir();
        if (dir) {
            Util.spawnCommandLine('python3 "' + dir + '/main.py" ' + arg);
        }
    },

    _setup_context_menu: function() {
        this.menuManager = new PopupMenu.PopupMenuManager(this);
        this.menu = new Applet.AppletPopupMenu(this, this.orientation);
        this.menuManager.addMenu(this.menu);

        let itemToggle = new PopupMenu.PopupMenuItem("Toggle Panel");
        itemToggle.connect("activate", () => this._send_cmd("--toggle"));
        this.menu.addMenuItem(itemToggle);

        let itemPref = new PopupMenu.PopupMenuItem("Preferences...");
        itemPref.connect("activate", () => this._send_cmd("--preferences"));
        this.menu.addMenuItem(itemPref);

        this.menu.addMenuItem(new PopupMenu.PopupSeparatorMenuItem());

        let itemQuit = new PopupMenu.PopupMenuItem("Quit Market Sync");
        itemQuit.connect("activate", () => this._send_cmd("--quit"));
        this.menu.addMenuItem(itemQuit);
    },

    _update: function() {
        try {
            if (GLib.file_test(STATUS_PATH, GLib.FileTest.EXISTS)) {
                let [ok, contents] = GLib.file_get_contents(STATUS_PATH);
                if (ok) {
                    let data = JSON.parse(contents.toString());
                    let text = data.markup || data.label || "Market Sync";
                    if (this._applet_label && this._applet_label.clutter_text) {
                        this._applet_label.clutter_text.set_markup(text);
                    } else {
                        this.set_applet_label(data.label || "Market Sync");
                    }
                    if (data.tooltip) {
                        this.set_applet_tooltip(data.tooltip);
                    }
                }
            } else {
                this.set_applet_label("Market Sync");
            }
        } catch (e) {
            // status file may be mid-write; ignore and retry next second
        }
    },

    on_applet_clicked: function(event) {
        this._send_cmd("--toggle");
    },

    on_applet_removed_from_panel: function() {
        if (this._timer_id) {
            GLib.source_remove(this._timer_id);
            this._timer_id = 0;
        }
    }
};

function main(metadata, orientation, panel_height, instance_id) {
    return new MarketSyncApplet(metadata, orientation, panel_height, instance_id);
}
