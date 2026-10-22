# SAFE SHIELD

The BPM lock's visible name is now **SAFE SHIELD**. Gameplay, original-BPM
protection, gift units, reservations/carry and API names are unchanged.

The user's `safe-shield-layout` PNGs and layout are preserved under
`SafeShieldAssets`. Native actors use normal alpha, with no added glow and
no mirroring of the right shield. The portrait coordinates are converted
uniformly at 0.32, matching the challenge HUD and existing BPM/receptors.

`SafeShield.lua` draws the shields, title and native Noto Sans JP Bold text
in both columns. Names remain fixed-size, fit the 320px reference budget by
ellipsis, and share the timer's baseline. The name/time group is centered
with a 10px gap and 80px reserved timer width; an empty name centers time alone.

`SafeShieldPresentation.lua` implements the supplied visibility and rounding:
ceil positive seconds, hide everything for zero/negative/nonfinite time or an
inactive effect. The existing game effect owns the clock. The existing clear
cue retains its two-beat priority before the shield presentation appears.

To reimport assets or deploy without changing settings:

    python Stream/safe_shield_design.py --layout <safe-shield-layout-folder>
    python Stream/safe_shield_design.py --root <portable-game-root>

Copy the updated `GiftAPI.lua` too when upgrading; the regular addon installer
includes everything. Browser source headings/stock labels also use SAFE SHIELD.
The HTTP route `/api/lock`, gift-map `kind=lock`, and `bpm_lock` status keys stay
unchanged for OneComme and existing integrations.

`SafeShieldPresentationTest.lua` runs in the engine alongside GiftRulesTest:
10/9.1/9/0.1 seconds, expiry, NaN/infinite/invalid inputs and name sanitation.
Native visual checks cover long-name ellipsis at fixed scale, empty/literal
names, 999s, whole-group expiry and both render columns.
