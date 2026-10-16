# Realistic medal presentation

Website medals now use six original fictional decoration designs: gold, silver and bronze season medals, a service cross, a combat medal and a Black Market medal. Textured ribbons and embossed metallic artwork replace the simple SVG symbols. Awards within each category share its artwork while keeping their distinct names, criteria and progress.

Larger presentation cards put earned awards first. Locked awards are subdued and labelled. Native keyboard-accessible buttons open a detailed inspection dialog with a larger medal, criteria and recorded recognition date. Profile-header season awards use the same medal artwork instead of emoji.

This update changes presentation only. Award IDs, stored achievements, season archives, ELO and wallet data are untouched. The realistic medals are fictional community decorations, not official military honours.

Deploy the complete package to the existing Railway service, preserve /data and variables, and refresh the website. No reset or new configuration is needed. It has not been deployed. Source artwork was inspected, but complete browser visual verification remains unavailable.

## Artwork
Built-in image generation was used. Project asset: web/medals-realistic.png. Final edit prompt: Preserve exactly these six gorgeous realistic medal designs and their 3-column by 2-row order. Re-layout as a precisely aligned sprite sheet with a TRANSPARENT background. Canvas 3:2 landscape. Each of six equal square cells contains one medal perfectly centered, scaled to no more than 75% of the cell height and 75% of its width. Mandatory empty transparent padding around ALL sides of EVERY medal including top ribbons and bottom edges: at least 12.5% cell padding. Top row must not touch bottom row. Remove all the cloudy coloured backdrop entirely leaving actual transparent alpha. Keep all intricate metallic and fabric detail and front facing proportions. No text or new objects. This is a functional website sprite sheet needing clear empty gutters.

The generated result retained a studio backdrop despite the transparency request; the website displays each decoration as an artwork tile. No transparency claim is made for the asset.
