window.GEOMOTION_TASKS = [
  {
    "id": "passage",
    "name": "Narrow-Passage Transport",
    "panel": "a",
    "description": "Reorient an elongated object to pass through a narrow opening and place it on the target pad. The object must maintain a feasible pose throughout transport, combining translation with rotation."
  },
  {
    "id": "book-slot",
    "name": "Upright Book Placement",
    "panel": "b",
    "description": "Place a book upright in a narrow slot. The task requires matching the object’s orientation to the slot and coordinating precise position and rotation during insertion."
  },
  {
    "id": "bottle",
    "name": "Oriented Bottle Placement",
    "panel": "c",
    "description": "Place a bottle inside a rack with its cap facing the opening. Reaching the target position is not enough: the bottle must satisfy the required final orientation."
  },
  {
    "id": "plate",
    "name": "Plate Pushing Around Obstacles",
    "panel": "d",
    "description": "Push a plate around obstacles and onto the target region while keeping it flat. The task tests whether the motion remains geometrically feasible throughout the route."
  },
  {
    "id": "book-drawer",
    "name": "Book Storage in a Drawer",
    "panel": "e",
    "description": "Store a book inside a drawer and close it. Object reorientation and placement must be coordinated with drawer operations to achieve the final configuration."
  },
  {
    "id": "mug",
    "name": "Single-Mug Alignment and Closure",
    "panel": "f",
    "description": "Place a mug in the storage box with its handle facing the back, then close the door. The task combines a specified object orientation with a sequential closure requirement."
  },
  {
    "id": "mango",
    "name": "Mango Transport and Avoidance",
    "panel": "g",
    "description": "Rotate the gripper to grasp across the mango’s shorter axis, then transport it to the target pad while keeping the nearby vase upright. Grasp alignment must account for the physical consequences of the subsequent motion."
  },
  {
    "id": "package",
    "name": "Package Storage and Drawer Closure",
    "panel": "h",
    "description": "Place a package inside the drawer and close it. The agent must coordinate object orientation, placement, and drawer motion under geometric and sequential constraints."
  },
  {
    "id": "two-mugs",
    "name": "Dual-Mug Alignment and Closure",
    "panel": "i",
    "description": "Place two mugs with different handle orientations—one toward the back and one toward the opening—then close the door. Both target orientations and the final door state must be satisfied."
  }
];
