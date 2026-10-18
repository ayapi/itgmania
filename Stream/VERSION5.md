# Version 6-2 additions — trial warnings and clear cues

This upgrade adds the 2026-10-14 warning/clear flow to Version 5-3. Native RGBA capture,
mirrored arrows, mat input, sound/pitch synchronization, note inventory and
fixed gift-name bubbles remain. No executable replacement is needed.

## Rules

- Rank is fixed at song start from TikTok + YouTube viewers: <50 / <150 / <350 /
  350+, requiring 1 / 1 / 2 / 4 trial or lock gift units. Normal rescue requires
  40 / 160 / 320 / 640pt; strong rescue requires 1.5 times that.
- The integer BPM offset is nonnegative, resets each song and never decays
  automatically. Safety cap is floor(original BPM × 15%).
- Auto +10 trials choose eight-measure boundaries after the first 24 measures
  and before the last 16. A first trial is planned whenever eligible boundaries
  exist; the second has a 50% chance when a later boundary exists. Active trials
  and locks defer auto trials; one boundary is rested after rescue.
- Strong trials raise BPM to the cap, reserve while busy or inside the intro,
  and carry if too late. Hearts are disabled for their first four measures;
  paid rescue and locks still work. Names show contributors or the last sender
  plus the number of other people.
- Every trial has a four-measure warning. Auto warnings begin four measures
  before their selected eight-measure start boundary (earliest measure 20).
  Fulfilled strong gifts warn on the next receiving beat, or after the intro,
  current trial or lock. No reserved attack skips the warning.
- The warning counts measures 4 → 3 → 2, then shows one large number per beat
  in the final measure (4 → 3 → 2 → 1 for 4/4). The game plays a short original
  notice chime and beat ticks; sounds play once, not in both browser sources.
  Speed and orange light begin only when the trial actually starts.
- Hearts during warnings are ignored. Paid rescue gifts retain the existing
  bank behavior and apply to the next trial, preserving their paid value.
- A lock during a warning reserves it again and restarts a full four-measure
  warning after the lock. Locking an active trial or filling its gauge shows
  `CHALLENGE CLEAR!` without a sender, for **two beats** (the user's shorter
  override of the document's one–two measure suggestion), with a short chime.
  The result counter updates immediately; the lock's own badge keeps its name.
- The player's native cue uses the native music beat. The stream's browser cue
  uses the same published beat and interpolates between polls; no timer in
  wall-clock seconds drives the countdown or clear duration. Strong names have
  fixed size and ellipsis. Warnings pending at exit retain paid reservations.
- 20 taps/reactions = 1pt. TikTok uses cumulative deltas and resets its baseline
  on trial start, after the blocked period, decreased totals, stream-ID changes,
  `reset:true`, or jumps beyond `tiktok_max_delta` (100000/update by default).
  YouTube adds every reaction type's per-event value.
- Heart credit is buffered and applied at at most one BPM per measure. Gift
  points bypass the speed limit, apply next beat and never lower BPM below the
  original. Outside-trial and surplus gift points are banked.
- Rescue under 20 seconds raises the next requirement by 20%; an unresolved
  trial lowers it by 20%. Calibration stays between 0.5–2 times rank base.
- Locks restore original BPM, resolve the trial and last four measures. At most
  two activate per song; queued locks chain. Partial, late and sold-out lock
  contributions carry. Trial contributions and reservations also carry.
- Notes retain the existing eighth-note plan, hold occupancy, two-foot limit,
  no consecutive added jumps and visible-field lead. Sold-out notes are rejected.
- Fail is Off and the gameplay life display is hidden in streamer mode.
  Combo remains; the browser shows a single rescue gauge and trial results.

Short songs without an eligible auto-trial interval report
`auto_trial_unavailable`. Auto trials cannot interrupt active paid effects.

## Local API

Send JSON to localhost:8765. Use a stable unique `event_id` for paid events;
duplicates return the prior receipt, and changed parameters return 409.
Inspect `/api/events/<event_id>` for contribution, reservation and carry outcomes.

| Endpoint | Body example |
| --- | --- |
| `/api/audience` | `{"tiktok":100,"youtube":50}` |
| `/api/hearts` | `{"platform":"tiktok","total":12345,"stream_id":"live-1"}` |
| `/api/hearts` | `{"platform":"youtube","reactions":[{"key":"🧡","value":3},{"key":"😄","value":1}]}` |
| `/api/rescue` | `{"event_id":"r1","sender":"視聴者A","points":2}` |
| `/api/trial` | `{"event_id":"t1","sender":"視聴者A","count":1}` |
| `/api/lock` | `{"event_id":"l1","sender":"視聴者A","count":1}` |
| `/api/notes` | `{"event_id":"n1","sender":"視聴者A","count":1}` |
| `/api/gift` | `{"event_id":"g1","sender":"視聴者A","platform":"youtube","gift_id":"actual-id","count":2}` |

TikTok accepts `reset:true`. YouTube alternatively accepts `count:4`.
Trial/lock/rescue events can wait between songs; notes require active gameplay.
Idle hearts are ignored, while idle TikTok totals set the next baseline.
`/api/tempo` returns 410; `/api/lock` now takes gift count rather than measures.

## Assignments and OBS

Actual gift IDs and images are undecided. `Save/GiftAPI/gift-map.json` starts
empty; unknown assignments are rejected. OneComme WebSocket ingestion is not
connected yet, as agreed. Its caller sends audience, gift and reaction data to
the APIs. Replace the map without rebuilding, for example:

```json
{"youtube":{"ACTUAL_ID":{"kind":"rescue","points_per_unit":2,
"name":"星","cost":2,"image_url":"https://example.com/gift.png"}},"tiktok":{}}
```

Trial/lock/note mappings use `kind` and `units_per_gift` (default 1). Select gift
events rather than Super Chats. The map also supplies menu names, images and
coin/jewel costs. No payment or platform action is performed by this addon.

Keep the existing browser source URL `/overlay`, 1080×1920 dimensions and game
capture transforms. Song information and NOTE ATTACK stay left; rank,
RESCUE/TRIAL/LOCK counts, gauge and brief rescue sender feed appear right.
Strong-trial status, enlarged contributors and the rescue gauge occupy the
center above native BPM; side menus only show gift/count information. anonymous hearts show no names.
The final line reports resolved trials / total trials.

Native BPM keeps its beat pulse and proportional font; the lock keeps its
fixed-size Noto name, ellipsis, gold badge and seconds. A separate browser source
`ITGmania 試練ライト` uses `/overlay?mode=light` and OBS `OBS_BLEND_SCREEN`.
Run `python configure_trial_light.py` while OBS and its WebSocket are running
to create/update it in the current scene, sized to the canvas and placed above
the camera but below the game and information. Existing source transforms are preserved.
The normal information source no longer contains the orange wash.
The dedicated source is opaque black when inactive (neutral in Screen mode),
and scales orange RGB brightness during trials; its alpha stays at 100%.
It follows the native song beat/effective BPM, compensates snapshot age and
interpolates at browser frame rate between polls. At >180 BPM it skips beats to
keep the smooth pulse at <=3Hz. Light strength varies from 12–50%; game arrows
and text sit above the light. Pausing, trial resolution, disconnection or stale
updates return the light to black.
Native edge illumination is removed, so game-source scale and phone cropping
cannot move or remove the effect. No audio capture or FFT is required.
Chroma key remains disabled for native transparent capture.

### Compact results in OBS

StreamerMode uses a transparent results card in both the normal left column
and the same right stream column as gameplay, preserving the OBS capture's
crop and transform. It contains the native Simply Love grade, total percent
score, and only FANTASTIC / EXCELLENT / GREAT / DECENT / WAY OFF / MISS counts.
The grade and percent use the existing native stage statistics and grade
thresholds. Hands, holds, mines, rolls, graphs and other panes are omitted.
Stage-stat storage and keyboard restart handling are preserved.

Evaluation publishes `screen: "evaluation"`, `evaluation_visible: true` and
`evaluation: {grade, score, percent, judgments}` at 10Hz. `ready` stays false
so note gifts cannot be placed after a song. The OBS controller displays
gameplay or a live evaluation heartbeat, hides on evaluation exit/selection,
and also hides stale/disconnected evaluation snapshots. Run
`python stream_results.py <runtime-root>` for the theme-only installer.

Only warning/clear additions from Version 6-2 are applied here. The user's
approved full-canvas Screen-blended orange light and metallic-gold lock badge
remain; the document's older edge-only light/blue-shield alternatives are not
used. Restart ITGmania once after updating theme files; the browser refreshes
without restarting OBS. `trial_notice_measures` defaults to 4 and
`trial_clear_beats` to 2 in `Save/GiftAPI/config.json`.

## State and tests

### Trial layout experiment (2026-10-18)

The order is judgment → four receptors → combo → trial/lock → BPM. Judgment
is at y=60, receptors at y=115, combo at y=164, player-side cue at y=248
and BPM at y=288 (480-high logical screen). The trial/BPM group is shifted
220 logical pixels from the original top layout, with enough clearance for
the larger browser trial panel below combo. Gift-note cards keep their positions.
`stream_hud_layout.py <runtime-root>` applies the matching theme anchors.
The OBS information source's `bpmBottom` anchor must receive the same shift
scaled by the current game source's vertical scale; capture transforms remain
unchanged. Trial panels stay above BPM, within the space below the receptors.

`start-test.cmd` no longer sends note additions by default. It continues hearts,
rescue points, strong trials and locks. `start-test.cmd --with-notes` restores
note additions explicitly; the real note-gift API and inventory are unchanged.

`bridge-state.json` persists paid receipt IDs and pending commands.
`trial-state.json` persists partial contributions, reserved strong trials,
banked points and calibration. The API collector checkpoints through the
existing asynchronous mailbox, away from the game render thread. Anonymous
heart receipts retain the last 128 entries. Back up state before resetting it.

Start through the existing `start-game.cmd`. Restart the API and game after
upgrading. `Save/GiftAPI/config.json` contains editable test values.
`start-test.cmd` sends rescue gifts every 3–10 seconds (optional notes every 3–6),
hearts every second, strong gifts every 35–55 and locks every 55–85. It posts
100 TikTok viewers before the next song; override with `--tiktok-viewers` and
`--youtube-viewers`. It no longer sends old ±BPM effects.

Run `python -m unittest discover -s Stream -p 'test_*.py'` for API/OBS tests.
`GiftRulesTest.lua` checks scheduling, rescue, persistence and note safety in
the actual engine's Lua VM. Native integration checks real inserted notes,
delayed strong trials, blocked hearts, paid rescue, chained locks and carry.
Local metrics include per-platform input, rank, trial duration/resolution,
points, contributions, note inventory, combo/judgments and processing time.

`node Stream/test_trial_pulse.cjs` verifies local beat interpolation, snapshot-age
compensation, speed changes, stale/error shutdown and pulse opacity/frequency.
