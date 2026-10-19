# New soldier artwork

The website shows one soldier per role, in three equipment stages that unlock with rank:

| Stage | Unlocks at | Look |
|---|---|---|
| 0 Basic issue | Private | Soft headwear, clean uniform, belt webbing, issued weapon. Fresh-faced. |
| 1 Field experienced | Corporal | Combat helmet, body armour, optics, radio. Worn kit, some dirt. |
| 2 Veteran specialist | Staff Sergeant | Night vision, plate carrier, comms headset, full specialist fit. Weathered, bearded or camo-painted. |

## How to make them

1. Generate 24 images: 8 roles × 3 stages. Use the same person for all three stages of a role, so the upgrade reads clearly.
2. Name them `<role>-<stage>.png`, for example `medic-1.png`. Roles: `rifle medic crew recon at lmg pilot engineer`.
3. Run `python scripts/prepare_soldier_art.py <folder>`. It removes backgrounds and writes `web/soldiers/*.webp`.

## Base prompt (use for every image)

> Photorealistic full-length portrait of a British Army soldier, standing three-quarter view, from head to mid-thigh, holding his weapon at the ready. Modern British MTP (Multicam) uniform, Union flag patch on the right shoulder. Natural soft studio lighting, sharp focus, high detail on fabric and kit, realistic skin. Plain flat light-grey background with no shadows, no scenery, no text, no logos, no watermark. Portrait 3:4. Same face and build as the other images in this set. {ROLE} {STAGE}

## Role details ({ROLE})

- **rifle**: Rifleman. SA80 A3 rifle.
- **medic**: Combat medic. Red-cross armband, medical pouches, SA80 carbine.
- **crew**: Armoured vehicle crewman. Olive one-piece coverall, crew helmet with headset, pistol on the chest.
- **recon**: Recce sniper. Long bolt-action sniper rifle with scope, scrim scarf.
- **at**: Anti-tank gunner. NLAW launcher on the shoulder.
- **lmg**: Support gunner. Belt-fed light machine gun with ammo belt.
- **pilot**: Army Air Corps helicopter pilot. Olive flight suit, survival vest, flight helmet with visor.
- **engineer**: Royal Engineer. Entrenching tool or breaching tool, extra pouches.

## Stage details ({STAGE})

- **stage 0**: Basic issue. Beret with cap badge (bush hat for recon, crew cap for crew, no helmet for pilot), clean new uniform, simple belt webbing, clean-shaven, young recruit.
- **stage 1**: Field experienced. Mk7 combat helmet with cover, Osprey body armour, optic on the weapon, personal radio, uniform sleeves rolled, light dirt and wear.
- **stage 2**: Veteran specialist. Helmet with night-vision mount and goggles, plate carrier loaded with pouches, comms headset, gloves, weathered face with stubble or camo cream, heavily used kit.

Keep the camera, lighting and framing the same across all 24 images so they sit together on the site.
