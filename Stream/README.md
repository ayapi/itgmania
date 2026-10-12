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
copy. `StreamMirror.lua` sets the two centers to 25% and 72% of window width,
with both receptor rows at the same Y position. At 1280 × 720, crop left
707/right 144 (429 × 720), then center this source horizontally in the portrait
canvas. No vertical offset is applied to the stream copy.
Gift cards stack beside the face with outer edges at ±143 logical units from the field center,
three per side. The stream's left/down arrows always use left cards; up/right
use right cards. Older cards sit above newer ones. They slide up in 160 ms on
arrival/reflow; they never scroll with the notes. Thin leaders follow the live
arrow position. Excess gift notes remain queued until one of six slots opens.
The newest cards align with BPM at Y=68, immediately above the receptors.
Cards fit their one/two-line text up to 76 units wide, with three units of
padding and two-unit gaps. Native BPM uses tighter glyph advance and grows to
fit the inner card edges, keeping one logical unit of clearance at peak pulse.

Start `Stream/start-api.cmd` for the local HTTP server on port 8765. Close the
old OutFox API server first when switching to this runtime. The request format
uses these endpoints:

- `POST /api/notes`: `{"sender":"viewer","count":3,"player":"P1"}`
- `POST /api/tempo`: `{"sender":"viewer","bpm_delta":10}`
- `POST /api/lock`: `{"sender":"viewer","measures":4}`
- `GET /api/status` and `GET /api/events/<event_id>` report readiness and results.

For OBS stream information, add a browser source with URL
`http://127.0.0.1:8765/overlay` (portrait canvas: 1080 × 1920, 30 FPS).
Keep the API bridge running. The page polls status four times per second,
displays song title/artist, stock, and recent tempo gifts with their sender and
BPM delta. It is transparent
outside the text/labels and hides when gameplay is inactive or the
heartbeat is disconnected. Edit `Stream/overlay.html` to adjust appearance.

Song information sits at the upper left, with a ♪ prefix on the title. Song
information and sender names prioritize Google Fonts Noto Color Emoji, with
Noto Sans JP for characters outside the emoji font. Loading these fonts needs
an Internet connection; the browser uses its sans-serif fallback otherwise.
Tempo gifts have no background box. Native sender names and deltas both use
Noto Sans JP Bold at the same size, with a crisp black stroke; only the delta's
fill changes to red/green. The game itself renders BPM above
the receptors, using Beast Machines lettering: cyan at the chart BPM, red above
it, green below it. Its 12% pulse follows the song beat, including rate changes,
stops and pauses; no extra timer or browser polling drives the animation.
Tempo gift names now render natively in the same update as the changed BPM,
for 0.8 seconds. Requests that only increase capped overflow do not show a name.
Up to three recent names stack above BPM; locked gifts appear at release if the
effective BPM changes. The browser suppresses its legacy tempo stack when
`native_tempo_notice` is true. Existing URL layout parameters remain available
for older game versions.
`prepare_overlay_font.py --root <runtime> --archive <font ZIP>` embeds the user's
local font in the runtime HTML. The repository contains no font data. Re-run
after replacing the HTML template; the Beast font importer also runs this step.
`prepare_stream_bpm_font.py --root <runtime> --archive <font ZIP>` generates
three local bitmap fonts for native BPM. It needs Pillow, and runs automatically
from the Beast font importer. Install these assets before loading GiftAPI.lua.
`prepare_stream_name_font.py --root <runtime>` generates cached Noto Sans JP
Bold pages and stroke textures for native names and lock labels (Pillow required). It downloads the
official Google Fonts variable TTF and OFL license to `Save/GiftAPI/font-cache`.
`--font <TTF>` can supply a local copy. The font covers 7,663 Latin, kana and
Japanese code-page characters. Missing characters use the game's default
fallback; this bitmap renderer does not implement the browser's color-emoji
sequence shaping. Native note labels use smaller text and retain two-line
wrapping and ellipsis. BPM and lock text fit with uniform scaling, never by
squeezing only the horizontal axis.
Unicode RANGE mappings avoid this engine version's broken `map U+...` parsing,
so supported Japanese glyphs come from Noto rather than the legacy fallback.
Streaming judgment movement takes 30 ms on entry and 70 ms on exit, while
retaining the 0.6-second readable hold. The installer applies this theme patch.

The status response retains song fields and `active_tempo_effects` as an empty
legacy array. Version 3 uses `tempo_feed` instead of expiring effects. A new
gameplay screen reloads the updated theme actor.

## Version 3 gift economy and gameplay

Tempo gifts are integer, cumulative changes to one song offset. They apply on
the next beat, persist without individual timers, and reset at the next song.
After four unlocked measures without another applied tempo gift, the offset
moves one BPM towards zero. Applied speed is limited to ±15% of the chart BPM
(rounded down to a whole BPM). Excess is retained internally, initially up to
±50% of the chart BPM. Beyond that limit, the API rejects the gift with a reason;
reducing an existing overflow remains possible after a chart BPM change.
`duration_seconds` is accepted as a deprecated compatibility field and ignored.

A lock fixes the current effective BPM for four measures per 500-yen block.
During it, decay pauses and tempo gifts are held. On release, held gifts apply
together before any reserved next lock starts. Lock inventory counts complete
blocks that still fit in the song, accounting for active and reserved locks.
Time-signature changes are supported. For charts with a large BPM change during
a lock, the ±15% safety limit takes priority over the locked numeric BPM.

NOTE ATTACK inventory is planned from the actual chart on eighth-note positions.
The planner considers holds, existing notes within half a beat, mines, two-foot
limits, and previous/next jump rows. It never introduces consecutive jumps.
The original chart is preserved. A gift reserves its count, shows immediate OBS
receipt feedback, then places real judged taps just below the visible field.
Unavailable insertion is retried rather than forcing a hold reset. Queues never
fall back to sixteenths. Stock shrinks as unused positions pass; sold-out or
oversized requests receive HTTP 409. Six visible cards, three per direction
group, remain the display limit.

Native HUD shows `BPM115(+7)`, a beat-synchronized pulse, active lock sender and
remaining seconds (e.g. `🔒テスト視聴者A 1.4s`) on a rounded metallic-gold badge, and a compact life gauge. Lock and tempo sender names retain a fixed text size and truncate with `…`. Standard ITGmania `EndOfSong`
failure mode keeps the song running through zero life and uses the engine's
existing end-of-song CLEAR/FAILED result. Combo and native note judgments remain.
Gift-modified scores do not replace the original chart's personal bests.
The white-framed life gauge sits midway between judgment and combo anchors,
including in the stream mirror. `stream_life.py` patches the theme's native life
metrics: streaming Casual mode uses ITG's gains/losses instead of Casual's zero
changes. Casual timing and scoring remain unchanged; normal non-streaming mode
keeps its original life rules. Restart the game after installing this patch.

OBS keeps song information, NOTE ATTACK on the left, BPM ATTACK / LOCK on the
right, and both remaining counts or SOLD OUT. Native tempo senders appear briefly
at application time, with consecutive repeats grouped as `A +1 x5`. Notifications
expire after 0.8 seconds; a lock-held gift is announced when actually applied.
The prices are initial display guidance: 10–20 / 50 / 100 yen equivalents for
±1 / ±5 / ±10, 100 yen per note, and 500 yen per four-measure lock.

Gift ID, coins, currency conversion and action selection stay with the caller
(e.g. OneComme). Optional API fields `platform`, `gift_id`, `amount_yen`, `coins`
and `viewer_count` are validated and recorded but do not alter the game effect.
No platform gift is assigned or charged by this API. Supply a unique `event_id`
to prevent duplicate delivery, and check `/api/events/<event_id>` for final
acceptance/completion. Receipt history is rotated in bounded status pages during
large bursts; lock completion IDs also resolve held-event receipts.

`Save/GiftAPI/config.json` exposes `tempo_limit_percent` (at most 0.15),
`tempo_stored_limit_percent` (initially 0.50), `tempo_decay_measures` (4),
`lock_min_measures` (4), and `tempo_notice_seconds` (0.8). Restart the bridge and
start a new song after editing configuration. The native status includes
`protocol_version: 3`, `bpm_offset`, `bpm_delta` (applied), `bpm_overflow`,
`pending_bpm_delta`, `bpm_lock`, `note_slots_total`, `note_remaining`,
`lock_remaining`, `life`, `failed`, `tempo_feed`, and `metrics`.

Local records are saved in `Save/GiftAPI/stream-metrics.jsonl`: accepted/rejected
gifts, receipt outcomes, BPM/overflow evolution, cap duration, lock use, note
inventory/consumption, life, combo breaks, native judgment/hold totals and failure result. Supplied price metadata
allows analysis by amount band without using viewer count as a safety control.
These personal stream records and locally generated fonts are excluded from Git.

Audio and note timing use the same native music rate. Names use stationary
cards with leaders following their notes, wrap to two lines and truncate with
`...`. They have opaque white backgrounds and black text. Existing notes and
hold/roll occupancy count toward the two-foot limit.

`Player:AddGiftTapNotes({{beat,column},...})` inserts only future taps, retains
the existing note results and reconstructs the affected iterator cursors. It does
not reload the player, replace the chart or reset a held note. Invalid batches
are rejected atomically. Modified plays are disqualified from chart best scores.

`Stream/start-test.cmd` sends test gifts during gameplay.
It sends +1 or -1 BPM with equal probability every 3–10 seconds, alternating
+10/-10 every 20–30 seconds, and a lock every 35–55 seconds when stock remains.
Notes still arrive every 3–6 seconds. `--small-tempo-min/max` and `--lock-min/max`
adjust the new intervals. Rejections show the API reason and do not restart the
other schedules.
`Stream/start-obs-sync.cmd` controls OBS opacity without stopping game capture;
Ctrl+C restores the prior source state and removes the temporary filter.
The installed `start-game.cmd` starts the API bridge and this OBS controller in
the background. `/api/info` identifies the API version and runtime directory;
the launcher reuses a matching server. The OBS controller refreshes the local
browser source after a bridge restart while preserving its URL layout settings.
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

The lock badge uses muted brushed gold with dark brown lettering. Tempo
notices use a thinner black outline and reserve the lane group width (240
logical units including the delta). Names keep their fixed size and truncate
only when that full line is exhausted. The three BPM HUD rows stack closely.
