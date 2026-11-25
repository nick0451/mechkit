# Material test bars (120 x 10 x 4 mm)

Print all three with the SAME settings you use for real parts (material, walls, infill, temperature).
`bar_upright.stl` stands 120 mm tall on a 10 x 4 mm base: add a brim (8 mm) in the slicer so it does not fall over.

## Sag test (stiffness): do it for each bar
1. Lay the bar over a table edge with 20 mm on the table; hold that end down hard (a clamp, or a book and a heavy
   weight). `bar_flat` and `bar_upright` lie on their 10 mm face; `bar_on_edge` stands on its 4 mm edge.
2. Mark a point 90 mm out from the table edge. Measure its height above the floor (or against a ruler).
3. Hang a known weight at that mark (a bag with something weighed on a kitchen scale; about 200 g for the flat and
   upright bars, about 1000 g for the on-edge bar). Measure the height again. The difference is the sag.
4. Tell Claude: the weight in grams and the sag in mm for each bar.

## Break test (strength), optional but valuable
Same set-up with `bar_upright` (it is the weak direction): add weight in steps until it snaps; report the last
weight it held and the weight that broke it. Wear eye protection; the pieces can fly.

Results go in with:  python -m mechkit.calibration fit --flat GRAMS:SAG --edge GRAMS:SAG --upright GRAMS:SAG --upright-break-g GRAMS
