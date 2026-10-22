# Native challenge design

Imported from the user's `parts/countdown-layout` and `parts/challenge-meter`
on 2026-10-22. Original RGBA PNGs are preserved, including their glow; sprites
use normal alpha blending. No browser capture or extra additive glow is used.

`ChallengeDesign.lua` contains the supplied countdown image rectangles relative
to the [550,1065] portrait anchor. Scale 0.32 matches the 800px reference lane
group to the native 256px lane group; y=208.8 preserves its distance below
native BPM y=164. BPM and receptors are not duplicated or moved.

`ChallengePresentation.lua` derives states from the music beat and actual
measure boundaries. Numbers flash for one beat at each remaining measure;
START lasts one beat. The existing trial rules, rate ramps, paid contribution
timing, locks and two-beat clear duration remain authoritative.

The meter uses the original 2048x256 layers, [72,80,1908,96] fill region,
cursor pivot [127,195], and right-aligned runtime current/required counter.
Both automatic and strong trials use the orange attack skin; clear uses cyan.
The +21 title uses original lettering. Other deltas use the supplied Oxanium
Bold bitmap font next to the original prefix; normal trials omit ATTACK.
Counters use the supplied Rajdhani Bold. OFL licenses and source fonts are
under `ChallengeAssets/licenses`; generated bitmap pages are prebuilt under
`ChallengeFonts`, so installation does not require Pillow.

To reimport/rebuild (Pillow required):

    python Stream/challenge_design.py --parts <parts-directory>

To deploy the assets/fonts without touching game preferences or HUD settings:

    python Stream/challenge_design.py --root <portable-game-root>

Also copy `ChallengeCue.lua` and `GiftRules.lua` into the gameplay overlay when
upgrading. The regular `Stream/install.py` includes these files and the design.
Restart the game after adding fonts. `ChallengePresentationTest.lua`, invoked
by `GiftRulesTest.lua` in the engine, checks measure flashes, waiting/START,
3/4 boundaries, progress, seek-back recalculation and two-beat clears.
