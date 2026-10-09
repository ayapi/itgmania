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

Start `Stream/start-api.cmd` for the local HTTP server on port 8765. Close the
old OutFox API server first when switching to this runtime. The request format
is unchanged:

- `POST /api/notes`: `{"sender":"viewer","count":3,"player":"P1"}`
- `POST /api/tempo`: `{"sender":"viewer","bpm_delta":10,"duration_seconds":20}`
- `GET /api/status` and `GET /api/events/<event_id>` report readiness and results.

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

Gift scheduling indexes occupied rows rather than repeatedly scanning the whole
chart, processes at most four insertions per frame, and reuses unchanged command
JSON. The game streams its transient status heartbeat; the bridge tolerates an
incomplete write for up to 0.3 seconds. `/api/status` includes `performance`
counters for the maximum addon update/insertion times and updates over 16.7 ms.
