// TEST DATA ONLY: a copy of Monitor weather display/exports/v0p9/presentation/manifest.json (taken 2026-11-25),
// limited to the keys in ../types.ts. Imported by the print tests; never by the app.
import type { Manifest } from "../types";

export const monitor: Manifest = {
 "project": "Monitor weather display",
 "version": "v0p9",
 "up": [
  0.0,
  0.0,
  1.0
 ],
 "assembled_bbox": [
  [
   -75.0,
   -57.6,
   -59.9161
  ],
  [
   75.0,
   9.9483,
   90.0
  ]
 ],
 "exploded_bbox": [
  [
   -24.0,
   -129.6,
   -56.44313644666139
  ],
  [
   43.1,
   108.4290753012208,
   25.4
  ]
 ],
 "exploded_offset": [
  0.0,
  0.0,
  206.443
 ],
 "parts": [
  {
   "key": "Bezel",
   "label": 1,
   "kind": "printed",
   "name": "Bezel",
   "part": "Bezel",
   "description": "Decorative gauge ring. Five pins on its back press into the pod face; held by friction, no glue.",
   "part_number": "MWD-P1",
   "material": "PETG",
   "colour": "#c8ccd2",
   "opacity": 1.0,
   "explode": [
    0.0,
    98.4807753012208,
    17.364817766693033
   ],
   "count": 1,
   "volume_mm3": 2387.9,
   "bbox": [
    [
     -24.0,
     -1.4216,
     -58.1796
    ],
    [
     24.0,
     9.9483,
     -10.5616
    ]
   ],
   "centre": [
    -0.0,
    4.34,
    -34.3404
   ],
   "bodies": 1,
   "step": "Bezel.step"
  },
  {
   "key": "Pod",
   "label": 2,
   "kind": "printed",
   "name": "Pod",
   "part": "Pod",
   "description": "Shell that holds the round display behind its window. Two M3 inserts in its back.",
   "part_number": "MWD-P2",
   "material": "PETG",
   "colour": "#2b2d31",
   "opacity": 1.0,
   "explode": [
    0.0,
    72.87577372290339,
    12.849965147352844
   ],
   "count": 1,
   "volume_mm3": 8358.18,
   "bbox": [
    [
     -24.0,
     -10.0879,
     -59.5688
    ],
    [
     24.0,
     7.1676,
     -5.0
    ]
   ],
   "centre": [
    -0.0,
    -1.9834,
    -27.422
   ],
   "bodies": 1,
   "step": "Pod.step"
  },
  {
   "key": "Display_Board",
   "label": 3,
   "kind": "bought",
   "name": "Display GC9A01 (board)",
   "part": "Round display GC9A01 1.28 in",
   "description": "1.28 inch round 240 x 240 display, 7-pin board with a tab. Seven wires soldered to its pads.",
   "part_number": "GC9A01-1.28",
   "material": "",
   "colour": "#2f6fb5",
   "opacity": 1.0,
   "explode": [
    0.0,
    39.39231012048832,
    6.945927106677213
   ],
   "count": 1,
   "volume_mm3": 2186.26,
   "bbox": [
    [
     -19.0,
     -5.9348,
     -54.0196
    ],
    [
     19.0,
     3.5419,
     -8.933
    ]
   ],
   "centre": [
    -0.0,
    -1.1716,
    -31.4065
   ],
   "bodies": 1,
   "step": "Display_Board.step"
  },
  {
   "key": "Display_Screen",
   "label": 3,
   "kind": "bought",
   "name": "Display GC9A01 (screen)",
   "part": "Round display GC9A01 1.28 in",
   "description": "1.28 inch round 240 x 240 display, 7-pin board with a tab. Seven wires soldered to its pads.",
   "part_number": "GC9A01-1.28",
   "material": "",
   "colour": "#0b0e11",
   "opacity": 1.0,
   "explode": [
    0.0,
    39.39231012048832,
    6.945927106677213
   ],
   "count": 0,
   "volume_mm3": 1678.34,
   "bbox": [
    [
     -17.8,
     -3.6298,
     -52.56
    ],
    [
     17.8,
     4.8107,
     -12.8088
    ]
   ],
   "centre": [
    -0.0,
    0.6579,
    -33.0672
   ],
   "bodies": 1,
   "step": "Display_Screen.step"
  },
  {
   "key": "Cover",
   "label": 4,
   "kind": "printed",
   "name": "Cover",
   "part": "Cover",
   "description": "Back plate of the pod. Four pads press the display board into its pocket; slot for the wires.",
   "part_number": "MWD-P3",
   "material": "PETG",
   "colour": "#3a3d42",
   "opacity": 1.0,
   "explode": [
    0.0,
    19.69615506024416,
    3.4729635533386065
   ],
   "count": 1,
   "volume_mm3": 4544.98,
   "bbox": [
    [
     -24.0,
     -12.0575,
     -59.9161
    ],
    [
     24.0,
     1.5523,
     -6.3892
    ]
   ],
   "centre": [
    0.0,
    -6.5287,
    -32.0466
   ],
   "bodies": 1,
   "step": "Cover.step"
  },
  {
   "key": "Clamp",
   "label": 5,
   "kind": "printed",
   "name": "Clamp",
   "part": "Clamp",
   "description": "Saddle over the monitor's bottom edge, with the tilted hanger for the pod and the back wall that carries the board.",
   "part_number": "MWD-P4",
   "material": "PETG",
   "colour": "#2b2d31",
   "opacity": 1.0,
   "explode": [
    0.0,
    0.0,
    0.0
   ],
   "count": 1,
   "volume_mm3": 23260.37,
   "bbox": [
    [
     -24.0,
     -34.7,
     -31.0665
    ],
    [
     41.5,
     3.0,
     25.4
    ]
   ],
   "centre": [
    3.8309,
    -19.1018,
    1.6325
   ],
   "bodies": 1,
   "step": "Clamp.step"
  },
  {
   "key": "Insert_M3_pod_L",
   "label": 6,
   "kind": "hardware",
   "name": "Insert M3 (pod, left)",
   "part": "Heat-set insert M3",
   "description": "Brass heat-set insert M3, 5.1 long, in a 4.0 mm hole. Set with a soldering iron.",
   "part_number": "MWD-H1",
   "material": "Brass",
   "colour": "#b8862b",
   "opacity": 1.0,
   "explode": [
    0.0,
    55.14923416868365,
    9.724297949348099
   ],
   "count": 1,
   "volume_mm3": 28.04,
   "bbox": [
    [
     -20.5,
     -7.7437,
     -23.6233
    ],
    [
     -16.5,
     -2.0265,
     -18.7985
    ]
   ],
   "centre": [
    -18.5,
    -4.8851,
    -21.2109
   ],
   "bodies": 1,
   "step": "Insert_M3_pod_L.step"
  },
  {
   "key": "Insert_M3_pod_R",
   "label": 6,
   "kind": "hardware",
   "name": "Insert M3 (pod, right)",
   "part": "Heat-set insert M3",
   "description": "Brass heat-set insert M3, 5.1 long, in a 4.0 mm hole. Set with a soldering iron.",
   "part_number": "MWD-H1",
   "material": "Brass",
   "colour": "#b8862b",
   "opacity": 1.0,
   "explode": [
    0.0,
    55.14923416868365,
    9.724297949348099
   ],
   "count": 1,
   "volume_mm3": 28.04,
   "bbox": [
    [
     16.5,
     -7.7437,
     -23.6233
    ],
    [
     20.5,
     -2.0265,
     -18.7985
    ]
   ],
   "centre": [
    18.5,
    -4.8851,
    -21.2109
   ],
   "bodies": 1,
   "step": "Insert_M3_pod_R.step"
  },
  {
   "key": "Insert_M3_cap",
   "label": 6,
   "kind": "hardware",
   "name": "Insert M3 (board cap)",
   "part": "Heat-set insert M3",
   "description": "Brass heat-set insert M3, 5.1 long, in a 4.0 mm hole. Set with a soldering iron.",
   "part_number": "MWD-H1",
   "material": "Brass",
   "colour": "#b8862b",
   "opacity": 1.0,
   "explode": [
    0.0,
    -10.0,
    0.0
   ],
   "count": 1,
   "volume_mm3": 28.04,
   "bbox": [
    [
     12.5,
     -32.0,
     11.0
    ],
    [
     16.5,
     -26.9,
     15.0
    ]
   ],
   "centre": [
    14.5,
    -29.45,
    13.0
   ],
   "bodies": 1,
   "step": "Insert_M3_cap.step"
  },
  {
   "key": "Bolt_M3x10_pod_L",
   "label": 7,
   "kind": "hardware",
   "name": "Bolt M3 x 10 (pod, left)",
   "part": "Bolt M3 x 10, socket head",
   "description": "Socket-head M3 x 10 machine screw.",
   "part_number": "MWD-H2",
   "material": "Steel",
   "colour": "#9aa0a8",
   "opacity": 1.0,
   "explode": [
    0.0,
    -29.544232590366242,
    -5.2094453300079095
   ],
   "count": 1,
   "volume_mm3": 141.96,
   "bbox": [
    [
     -21.25,
     -16.7372,
     -25.9248
    ],
    [
     -15.75,
     -3.1967,
     -19.4819
    ]
   ],
   "centre": [
    -18.5,
    -11.5951,
    -22.3941
   ],
   "bodies": 1,
   "step": "Bolt_M3x10_pod_L.step"
  },
  {
   "key": "Bolt_M3x10_pod_R",
   "label": 7,
   "kind": "hardware",
   "name": "Bolt M3 x 10 (pod, right)",
   "part": "Bolt M3 x 10, socket head",
   "description": "Socket-head M3 x 10 machine screw.",
   "part_number": "MWD-H2",
   "material": "Steel",
   "colour": "#9aa0a8",
   "opacity": 1.0,
   "explode": [
    0.0,
    -29.544232590366242,
    -5.2094453300079095
   ],
   "count": 1,
   "volume_mm3": 141.96,
   "bbox": [
    [
     15.75,
     -16.7372,
     -25.9248
    ],
    [
     21.25,
     -3.1967,
     -19.4819
    ]
   ],
   "centre": [
    18.5,
    -11.5951,
    -22.3941
   ],
   "bodies": 1,
   "step": "Bolt_M3x10_pod_R.step"
  },
  {
   "key": "Bolt_M3x10_cap",
   "label": 7,
   "kind": "hardware",
   "name": "Bolt M3 x 10 (board cap)",
   "part": "Bolt M3 x 10, socket head",
   "description": "Socket-head M3 x 10 machine screw.",
   "part_number": "MWD-H2",
   "material": "Steel",
   "colour": "#9aa0a8",
   "opacity": 1.0,
   "explode": [
    0.0,
    -68.0,
    0.0
   ],
   "count": 1,
   "volume_mm3": 141.96,
   "bbox": [
    [
     11.75,
     -38.0,
     10.25
    ],
    [
     17.25,
     -25.0,
     15.75
    ]
   ],
   "centre": [
    14.5,
    -33.2635,
    13.0
   ],
   "bodies": 1,
   "step": "Bolt_M3x10_cap.step"
  },
  {
   "key": "Jaw",
   "label": 8,
   "kind": "printed",
   "name": "Jaw",
   "part": "Jaw",
   "description": "Pressure plate between the clamp screw and the monitor's back. Spreads the grip so the unit cannot twist.",
   "part_number": "MWD-P5",
   "material": "PETG",
   "colour": "#8a8f98",
   "opacity": 1.0,
   "explode": [
    0.0,
    13.0,
    0.0
   ],
   "count": 1,
   "volume_mm3": 2354.29,
   "bbox": [
    [
     -22.0,
     -24.5,
     1.5
    ],
    [
     22.0,
     -21.5,
     19.5
    ]
   ],
   "centre": [
    -0.0,
    -22.9917,
    10.4862
   ],
   "bodies": 1,
   "step": "Jaw.step"
  },
  {
   "key": "Insert_M4_clamp",
   "label": 9,
   "kind": "hardware",
   "name": "Insert M4 (clamp)",
   "part": "Heat-set insert M4",
   "description": "Brass heat-set insert M4 in a 4.5 mm pocket, set from inside the saddle so clamping seats it.",
   "part_number": "MWD-H3",
   "material": "Brass",
   "colour": "#b8862b",
   "opacity": 1.0,
   "explode": [
    0.0,
    6.0,
    0.0
   ],
   "count": 1,
   "volume_mm3": 13.35,
   "bbox": [
    [
     -2.25,
     -30.0,
     9.75
    ],
    [
     2.25,
     -26.0,
     14.25
    ]
   ],
   "centre": [
    -0.0,
    -28.0,
    12.0
   ],
   "bodies": 1,
   "step": "Insert_M4_clamp.step"
  },
  {
   "key": "Screw_M4x30",
   "label": 10,
   "kind": "hardware",
   "name": "Clamp screw M4 x 30",
   "part": "Screw M4 x 30, socket head",
   "description": "Socket-head M4 x 30: the clamp screw. Runs through the M4 insert and presses on the jaw.",
   "part_number": "MWD-H4",
   "material": "Steel",
   "colour": "#9aa0a8",
   "opacity": 1.0,
   "explode": [
    0.0,
    -40.0,
    0.0
   ],
   "count": 1,
   "volume_mm3": 530.93,
   "bbox": [
    [
     -3.5,
     -57.3,
     8.5
    ],
    [
     3.5,
     -23.3,
     15.5
    ]
   ],
   "centre": [
    0.0,
    -43.229,
    12.0
   ],
   "bodies": 1,
   "step": "Screw_M4x30.step"
  },
  {
   "key": "Knob",
   "label": 11,
   "kind": "printed",
   "name": "Knob",
   "part": "Knob",
   "description": "Thumb knob pressed onto the clamp screw's head.",
   "part_number": "MWD-P6",
   "material": "PETG",
   "colour": "#b0343a",
   "opacity": 1.0,
   "explode": [
    0.0,
    -72.0,
    0.0
   ],
   "count": 1,
   "volume_mm3": 1824.48,
   "bbox": [
    [
     -8.8854,
     -57.6,
     3.1146
    ],
    [
     8.8854,
     -48.6,
     20.8854
    ]
   ],
   "centre": [
    -0.0,
    -52.9587,
    12.0
   ],
   "bodies": 1,
   "step": "Knob.step"
  },
  {
   "key": "Board",
   "label": 12,
   "kind": "bought",
   "name": "ESP32-C3 SuperMini",
   "part": "ESP32-C3 SuperMini",
   "description": "Microcontroller board, 22.5 x 18 mm, USB-C pointing up. Sits on the back wall with its lower edge in the ledge.",
   "part_number": "ESP32-C3-SuperMini",
   "material": "",
   "colour": "#3f8a4a",
   "opacity": 1.0,
   "explode": [
    0.0,
    -22.0,
    0.0
   ],
   "count": 1,
   "volume_mm3": 687.6,
   "bbox": [
    [
     20.4,
     -36.4,
     1.5
    ],
    [
     38.4,
     -32.0,
     25.2
    ]
   ],
   "centre": [
    29.4,
    -33.245,
    15.3741
   ],
   "bodies": 1,
   "step": "Board.step"
  },
  {
   "key": "Board_Cap",
   "label": 13,
   "kind": "printed",
   "name": "Board_Cap",
   "part": "Board_Cap",
   "description": "Cap over the board. Hooks round the end of the back wall and is bolted on; takes the pull when the cable is unplugged.",
   "part_number": "MWD-P7",
   "material": "PETG",
   "colour": "#4a4e55",
   "opacity": 1.0,
   "explode": [
    0.0,
    -46.0,
    0.0
   ],
   "count": 1,
   "volume_mm3": 2529.57,
   "bbox": [
    [
     10.5,
     -38.6,
     -0.5
    ],
    [
     43.1,
     -24.6,
     25.4
    ]
   ],
   "centre": [
    29.6491,
    -35.4932,
    12.9215
   ],
   "bodies": 1,
   "step": "Board_Cap.step"
  },
  {
   "key": "Monitor",
   "label": 0,
   "kind": "reference",
   "name": "Monitor (for context)",
   "part": "Monitor (for context)",
   "description": "Piece of the monitor's bottom edge: 21.5 mm thick where the clamp sits.",
   "part_number": "",
   "material": "",
   "colour": "#3a3d42",
   "opacity": 0.25,
   "explode": [
    0.0,
    0.0,
    0.0
   ],
   "count": 1,
   "volume_mm3": 290250.0,
   "bbox": [
    [
     -75.0,
     -21.5,
     0.0
    ],
    [
     75.0,
     0.0,
     90.0
    ]
   ],
   "centre": [
    0.0,
    -10.75,
    45.0
   ],
   "bodies": 1,
   "step": "Monitor.step"
  }
 ],
 "views": [
  {
   "name": "Front",
   "eye": [
    140.0,
    250.0,
    40.0
   ],
   "target": [
    0.0,
    -14.0,
    -14.0
   ],
   "up": [
    0.0,
    0.0,
    1.0
   ],
   "group": "assembled"
  },
  {
   "name": "Side",
   "eye": [
    330.0,
    -15.0,
    -10.0
   ],
   "target": [
    0.0,
    -14.0,
    -14.0
   ],
   "up": [
    0.0,
    0.0,
    1.0
   ],
   "group": "assembled"
  },
  {
   "name": "Rear",
   "eye": [
    120.0,
    -260.0,
    60.0
   ],
   "target": [
    0.0,
    -22.0,
    -8.0
   ],
   "up": [
    0.0,
    0.0,
    1.0
   ],
   "group": "assembled"
  },
  {
   "name": "Exploded",
   "eye": [
    330.0,
    150.0,
    150.0
   ],
   "target": [
    0.0,
    -20.0,
    -10.0
   ],
   "up": [
    0.0,
    0.0,
    1.0
   ],
   "group": "exploded"
  },
  {
   "name": "Exploded rear",
   "eye": [
    300.0,
    -260.0,
    150.0
   ],
   "target": [
    0.0,
    -20.0,
    -10.0
   ],
   "up": [
    0.0,
    0.0,
    1.0
   ],
   "group": "exploded"
  }
 ],
 "table": [
  {
   "label": 1,
   "part": "Bezel",
   "qty": 1,
   "kind": "printed",
   "made": "3D printed",
   "material": "PETG",
   "part_number": "MWD-P1",
   "description": "Decorative gauge ring. Five pins on its back press into the pod face; held by friction, no glue."
  },
  {
   "label": 2,
   "part": "Pod",
   "qty": 1,
   "kind": "printed",
   "made": "3D printed",
   "material": "PETG",
   "part_number": "MWD-P2",
   "description": "Shell that holds the round display behind its window. Two M3 inserts in its back."
  },
  {
   "label": 3,
   "part": "Round display GC9A01 1.28 in",
   "qty": 1,
   "kind": "bought",
   "made": "bought",
   "material": "",
   "part_number": "GC9A01-1.28",
   "description": "1.28 inch round 240 x 240 display, 7-pin board with a tab. Seven wires soldered to its pads."
  },
  {
   "label": 4,
   "part": "Cover",
   "qty": 1,
   "kind": "printed",
   "made": "3D printed",
   "material": "PETG",
   "part_number": "MWD-P3",
   "description": "Back plate of the pod. Four pads press the display board into its pocket; slot for the wires."
  },
  {
   "label": 5,
   "part": "Clamp",
   "qty": 1,
   "kind": "printed",
   "made": "3D printed",
   "material": "PETG",
   "part_number": "MWD-P4",
   "description": "Saddle over the monitor's bottom edge, with the tilted hanger for the pod and the back wall that carries the board."
  },
  {
   "label": 6,
   "part": "Heat-set insert M3",
   "qty": 3,
   "kind": "hardware",
   "made": "hardware",
   "material": "Brass",
   "part_number": "MWD-H1",
   "description": "Brass heat-set insert M3, 5.1 long, in a 4.0 mm hole. Set with a soldering iron."
  },
  {
   "label": 7,
   "part": "Bolt M3 x 10, socket head",
   "qty": 3,
   "kind": "hardware",
   "made": "hardware",
   "material": "Steel",
   "part_number": "MWD-H2",
   "description": "Socket-head M3 x 10 machine screw."
  },
  {
   "label": 8,
   "part": "Jaw",
   "qty": 1,
   "kind": "printed",
   "made": "3D printed",
   "material": "PETG",
   "part_number": "MWD-P5",
   "description": "Pressure plate between the clamp screw and the monitor's back. Spreads the grip so the unit cannot twist."
  },
  {
   "label": 9,
   "part": "Heat-set insert M4",
   "qty": 1,
   "kind": "hardware",
   "made": "hardware",
   "material": "Brass",
   "part_number": "MWD-H3",
   "description": "Brass heat-set insert M4 in a 4.5 mm pocket, set from inside the saddle so clamping seats it."
  },
  {
   "label": 10,
   "part": "Screw M4 x 30, socket head",
   "qty": 1,
   "kind": "hardware",
   "made": "hardware",
   "material": "Steel",
   "part_number": "MWD-H4",
   "description": "Socket-head M4 x 30: the clamp screw. Runs through the M4 insert and presses on the jaw."
  },
  {
   "label": 11,
   "part": "Knob",
   "qty": 1,
   "kind": "printed",
   "made": "3D printed",
   "material": "PETG",
   "part_number": "MWD-P6",
   "description": "Thumb knob pressed onto the clamp screw's head."
  },
  {
   "label": 12,
   "part": "ESP32-C3 SuperMini",
   "qty": 1,
   "kind": "bought",
   "made": "bought",
   "material": "",
   "part_number": "ESP32-C3-SuperMini",
   "description": "Microcontroller board, 22.5 x 18 mm, USB-C pointing up. Sits on the back wall with its lower edge in the ledge."
  },
  {
   "label": 13,
   "part": "Board_Cap",
   "qty": 1,
   "kind": "printed",
   "made": "3D printed",
   "material": "PETG",
   "part_number": "MWD-P7",
   "description": "Cap over the board. Hooks round the end of the back wall and is bolted on; takes the pull when the cable is unplugged."
  }
 ],
 "steps": [
  {
   "title": "Set the inserts in the pod",
   "text": "Press the two M3 inserts into the holes in the pod's back with a soldering iron, flush with the surface.",
   "add": [
    "Pod",
    "Insert_M3_pod_L",
    "Insert_M3_pod_R"
   ]
  },
  {
   "title": "Set the inserts in the clamp",
   "text": "M3 insert into the back wall from behind (for the board cap). M4 insert into its pocket from INSIDE the saddle, so that clamping pushes it against the pocket's floor.",
   "add": [
    "Clamp",
    "Insert_M3_cap",
    "Insert_M4_clamp"
   ]
  },
  {
   "title": "Wire and seat the display",
   "text": "Solder the seven wires to the display's pads (see pinmap.json). Lay the display in the pod, screen toward the window, tab toward the flat top. The ribbon fold and the solder ends have their own reliefs.",
   "add": [
    "Display_Board",
    "Display_Screen"
   ]
  },
  {
   "title": "Close the pod and hang it on the clamp",
   "text": "Feed the wires through the slot in the cover and the hanger. Put the cover on, hold the pod against the hanger and fasten with two M3 x 10 bolts from behind.",
   "add": [
    "Cover",
    "Bolt_M3x10_pod_L",
    "Bolt_M3x10_pod_R"
   ]
  },
  {
   "title": "Press on the bezel",
   "text": "Line up the five pins with the holes in the pod's face and press. It holds by friction; no glue needed.",
   "add": [
    "Bezel"
   ]
  },
  {
   "title": "Fit the board and its cap",
   "text": "Solder the wires to the ESP32-C3 board. Tuck its lower edge behind the ledge lip on the back wall, USB socket up. Hook the cap round the end of the wall and fasten it with one M3 x 10 bolt.",
   "add": [
    "Board",
    "Board_Cap",
    "Bolt_M3x10_cap"
   ]
  },
  {
   "title": "Fit the clamp screw",
   "text": "Press the knob onto the M4 x 30 screw's head. Run the screw through the M4 insert from behind. Stand the jaw in the saddle with its socket on the screw's tip. Hang the unit on the monitor's bottom edge and tighten gently.",
   "add": [
    "Screw_M4x30",
    "Knob",
    "Jaw"
   ]
  }
 ]
};
