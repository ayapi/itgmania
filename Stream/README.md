# Simply Love streaming fork

This fork adds native RGBA output on Windows and real, judged gift taps to
ITGmania. The upstream ITGmania and Simply Love licenses apply; this addon is
also GPL-3.0-or-later.

Run `python Stream/install.py` in a portable runtime with Simply Love. It adds
the theme overlay and sets `StreamerMode=1` in `Save/Preferences.ini`. This
preference takes effect when the game starts: it requests eight alpha bits for
the window framebuffer. The theme clears the gameplay background to transparent
and hides the upper gameplay UI. Normal mode remains available with
`StreamerMode=0` and a game restart.

Enable **Allow transparency** on an OBS game-capture source targeting
`ITGmania.exe`. Check the premultiplied-alpha setting against the emitted capture.
Disable chroma key when testing the native transparent output.

In streaming mode, dance-single gameplay places the normal P1 field on the
left and a rendering copy on the right. The copy rotates note/receptor arrows
180 degrees and reverses lane order without changing scrolling direction. It shares
P1's judgments, combo, gift notes and readable name labels; P2 is not joined
and gameplay is updated only once. Actual two-player play does not use this
copy. `StreamMirror.lua` sets the two centers to 25% and 72% of window width.
To capture the right copy, shift an existing P1 crop right by
`stream_mirror_offset_pixels` from `/api/status`. At 1280 pixels wide this is
602 pixels: a crop of left 120/right 663 becomes left 722/right 61, preserving
the source width, OBS scale and placement.
Gift labels sit four logical units outside the 64-unit arrow edge to keep
the portrait capture narrow. The above crop is 497 by 720 pixels at 1280 by 720.

Start `Stream/start-api.cmd` for the local HTTP server on port 8765. Close the
old OutFox API server first when switching to this runtime. The request format
is unchanged:

- `POST /api/notes`: `{"sender":"viewer","count":3,"player":"P1"}`
- `POST /api/tempo`: `{"sender":"viewer","bpm_delta":10,"duration_seconds":20}`
- `GET /api/status` and `GET /api/events/<event_id>` report readiness and results.

For OBS stream information, add a browser source with URL
`http://127.0.0.1:8765/overlay` (portrait canvas: 1080 × 1920, 30 FPS).
Keep the API bridge running. The page polls status four times per second,
displays the effective BPM, song title/artist, and individually active tempo
gifts with their sender and BPM delta. It is transparent
outside the text/labels and hides when gameplay is inactive or the
heartbeat is disconnected. Edit `Stream/overlay.html` to adjust appearance.

Song information sits at the upper left. BPM sits above the receptors with
Beast Machines lettering: cyan at the chart BPM, red above it, green below it.
Older tempo gifts appear above newer gifts; new rows slide in and push existing
rows upwards in 160 ms. URL parameters `bpmX` and `bpmBottom` position this stack
in canvas pixels. Keep the browser source at 0,0 with scale 1. Match its BPM
anchor to the OBS game source after moving or resizing that source.
`prepare_overlay_font.py --root <runtime> --archive <font ZIP>` embeds the user's
local font in the runtime HTML. The repository contains no font data. Re-run
after replacing the HTML template; the Beast font importer also runs this step.
Streaming judgment movement takes 30 ms on entry and 70 ms on exit, while
retaining the 0.6-second readable hold. The installer applies this theme patch.

The status response adds `song_title`, `song_artist`, and
`active_tempo_effects`, a list of `{event_id, sender, bpm_delta,
remaining_seconds}` objects. Existing fields and gift endpoints remain
compatible. A new gameplay screen reloads the updated theme actor.

Tempo deltas add together and each effect expires independently. Audio and note
timing use the same native music rate. Names follow their notes in a right-hand
column, wrap to two lines and truncate with `...`. They have opaque white
backgrounds and black text. Gift taps use eighth-note rows by default; a backlog
of 48 or more taps enables sixteenth-note rows. Existing notes and hold/roll
occupancy count toward the two-foot limit.

`Player:AddGiftTapNotes({{beat,column},...})` inserts only future taps, retains
the existing note results and reconstructs the affected iterator cursors. It does
not reload the player, replace the chart or reset a held note. Invalid batches
are rejected atomically. Modified plays are disqualified from chart best scores.

`Stream/start-test.cmd` sends test gifts during gameplay.
`Stream/start-obs-sync.cmd` controls OBS opacity without stopping game capture;
Ctrl+C restores the prior source state and removes the temporary filter.
The installed `start-game.cmd` also starts this OBS controller in the background.
Only one controller runs per OBS server. A restart removes leftover controller
filters after an interrupted shutdown, without removing chroma key, crop or
other user filters.

New installations use speed-dependent pitch (`RateModPreservesPitch=0`).
To import the locally installed OutFox SCH-CLASSIC-SMNOTE skin and its beat bars,
run `python Stream/import_outfox_style.py --outfox "C:/Games/OutFox 0.5.0 Alpha Win64"`.
The importer copies assets only into the local runtime and leaves OutFox intact.

The streaming overlay uses compact, rounded gift labels and fades the top edge
into transparency without dimming RGB. Judgment and combo feedback sits just
below the receptors. Menus and song previews are silent while gameplay audio
and menu sound effects remain enabled.

The installed `start-game.cmd` launches a background window-position tracker.
It saves normal window coordinates in `Save/WindowPosition.json`, restores them
on the next launch, and keeps the title bar reachable after monitor changes.
Launch through this command file to enable position restoration.

To import foot-pad bindings, run `python Stream/import_outfox_input.py --outfox
"C:/Games/OutFox 0.5.0 Alpha Win64"`. OutFox's `Joy1_Button 3` must be converted
to ITGmania's `Joy1_B3`; a direct Keymaps.ini copy does not work. The importer
backs up the destination before replacing bindings. The deployed setup also
uses `AutoMapOnJoyChange=0` in `Save/Preferences.ini` to preserve manual mapping,
and `ShowMouseCursor=1` in `Data/Static.ini` to keep the mouse visible.

Custom Beast Machines assets are generated locally from the user's font ZIP:

```powershell
python -m pip install Pillow
python Stream/import_beast_font.py --root "C:/path/to/portable-game" --archive "C:/path/to/beast-machines-cufonfonts.zip"
```

The generator creates the judgment sprite sheet and combo bitmap font, applies
one text size to all judgments, and adds spacing between outlined letters.
Restart the game after regenerating its textures. Font files, generated custom
font assets, OutFox skins, songs, and local OBS credentials are not bundled in
this repository.

Gift scheduling indexes occupied rows rather than repeatedly scanning the whole
chart, processes at most four insertions per frame, and reuses unchanged command
JSON. The game streams its transient status heartbeat; the bridge tolerates an
incomplete write for up to 0.3 seconds. `/api/status` includes `performance`
counters for the maximum addon update/insertion times and updates over 16.7 ms.

The native gameplay mailbox reads commands and publishes status on a background
thread. The render thread exchanges JSON strings in memory; /api/status also
reports mailbox_async, ps and per-operation/frame timing counters.
