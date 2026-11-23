# Neo-flood-fill
# Flood Fill & BFS Pathfinding Visualizer

A Python research project implementing, testing, and visualizing two Flood Fill algorithms — **Recursive** and **Queue-based (BFS)** — with an interactive Pygame GUI for BFS pathfinding.

---

## What is Flood Fill?

**Flood Fill** is an algorithm that starts from a given cell and spreads outward to fill all connected cells of the same type — similar to how water floods from a single source, or how the **paint bucket tool** works in image editors like Photoshop or MS Paint.

---

## What does this project do?

This project researches and implements Flood Fill from scratch in Python, comparing two different approaches:

| | Recursive | Queue-based (BFS) |
|---|---|---|
| Traversal | Depth-first (DFS) | Breadth-first (BFS) |
| Stack overflow risk | ⚠️ Yes | ✅ No |
| Finds shortest path | ❌ No | ✅ Yes |

Beyond just filling, we extend the BFS approach to **find the shortest path** between two points on a grid — visualized step-by-step in both the console and a Pygame GUI.

### Why Flood Fill for this project?

Flood Fill is a foundational algorithm that bridges simple graph traversal (DFS/BFS) with real visual applications. It is concrete enough to implement from scratch, testable with clear pass/fail criteria, and complex enough to explore meaningful trade-offs such as recursion limits, memory usage, and pathfinding extensions. It also lends itself naturally to visualization, making it ideal for a research project that includes both algorithmic analysis and a working GUI.

---

## Project Structure

```
phase2_Pygame.ipynb   ← Main notebook (all code + tests + visualizer)
README.md             ← This file
```

The notebook is organized into 7 sections:

| Section | Description |
|---|---|
| **1. Grid Design** | Core 2D grid data structure and helper functions |
| **2. Recursive Flood Fill** | Algorithm 1 — DFS-based implementation |
| **3. Queue-based Flood Fill** | Algorithm 2 — BFS-based implementation |
| **4. Step-by-step Visualization** | Console animation of BFS exploring and tracing path |
| **5. Unit Tests** | 44 tests across 7 groups validating both algorithms |
| **6. Complexity Analysis** | Time O(N) and Space O(N) verified with measurements |
| **7. Pygame Visualizer** | Interactive GUI with live BFS pathfinding animation |

---

## Section 1 — Grid Design

The grid is represented as a **2D Python list** where each cell stores an integer:

| Value | Constant | Meaning |
|---|---|---|
| `0` | `EMPTY` | Passable, unfilled cell |
| `1` | `WALL` | Impassable barrier |
| `2` | `FILLED` | Already marked cell |

Six helper functions abstract all grid operations:

| Function | Purpose |
|---|---|
| `create_grid(rows, cols)` | Build a fresh grid initialized to `EMPTY` |
| `print_grid(grid)` | Display the grid in the console |
| `is_valid_cell(grid, row, col)` | Check if a position is inside the grid |
| `get_cell(grid, row, col)` | Safely read a cell's value |
| `set_cell(grid, row, col, value)` | Safely write a value to a cell |
| `get_grid_size(grid)` | Return `(rows, cols)` dimensions |

> Using `is_valid_cell` as a boundary guard on every read/write prevents index-out-of-range errors — especially important in recursive code.

---

## Section 2 — Recursive Flood Fill

### What is it?
The recursive approach implements flood fill by having each cell call the same function on its neighbors — a classic **Depth-First Search (DFS)** pattern.

### How it works:
```
1. If the current cell is out of bounds OR doesn't match target_color → STOP
2. Paint the current cell with fill_color
3. Recursively call the same function on all 4 neighbors (up, down, left, right)
```

### Visualization:
```
Start at (0,0)        Step 1            Step 2
. . . .               F . . .           F F . .
. . . .       →       F . . .    →      F F . .
. ■ . .               . ■ . .           . ■ . .
```
*(F = filled, ■ = wall)*

### Advantages:
- Very simple and intuitive to read and implement
- Mirrors the natural recursive definition of "connected region"

### Disadvantages:
- **Stack overflow risk** — Python's default recursion limit is ~1000 frames. A fully open 32×32 grid (1024 cells) can crash the program with `RecursionError`
- Follows DFS order — does NOT guarantee shortest path
- Higher memory overhead per cell (full stack frame per recursive call)

---

## Section 3 — Queue-based (BFS) Flood Fill

### What is it?
The queue-based approach replaces the call stack with an explicit `deque`, making the algorithm fully iterative — no recursion, no stack overflow risk. It follows a **Breadth-First Search (BFS)** pattern.

### How it works:
```
1. Add start cell to queue. Paint it immediately.
2. While queue is not empty:
      Take first cell from queue (FIFO)
      Check all 4 neighbors
      If neighbor is valid AND matches target_color:
          Paint it → Add to queue
3. Queue empty → done
```

### Key difference from Recursive (DFS vs BFS):
BFS expands cells **layer by layer** — all cells at distance 1 first, then distance 2, and so on. This is what allows BFS to guarantee the shortest path.

```
Step 1        Step 2        Step 3
. . . .       . 1 . .       . 1 2 .
. S . .  →    . S 1 .  →    . S 1 2
. . . .       . 1 . .       . 1 2 .
```
*(Numbers show which "wave" reached each cell. S = Start)*

### Shortest path via Parent Map:
When each cell is discovered, BFS records which cell it came from:
```python
parent[(r, c)] = (previous_row, previous_col)
```
Once the end cell is reached, we **backtrack through the parent map** to reconstruct the shortest path:
```
End → parent[End] → parent[...] → Start
Reversed → Start → ... → End  Shortest path!
```

### Advantages:
- No stack overflow — safe on any grid size
- Guarantees shortest path (BFS layer-by-layer property)
- Lower memory per cell (only stores `(row, col)` tuples in queue)

### Disadvantages:
- Slightly more code than recursive version
- Uses extra memory for the `visited` set and `parent` dictionary

---

## Section 4 — Step-by-step Console Visualization

The function `flood_fill_queue_steps()` animates the BFS in two phases directly in the console:

**Phase 1 — Search:** BFS explores the grid cell by cell, printing the grid after each discovery. Visited cells are marked with a special color value.

**Phase 2 — Path trace:** Once the end cell is found, the shortest path is traced backward through the parent map and drawn cell by cell from start to end.

```
Phase 1 (BFS exploring):      Phase 2 (Shortest path):
2 1 0 0 0                     X 1 0 0 0
2 0 1 0 0                     X 0 1 0 0
2 2 0 0 0    →                X X 0 0 0
0 0 0 0 0                     0 0 X 0 0
0 0 0 0 E                     0 0 0 X X
```

The `delay` parameter (in seconds) controls animation speed.

---

## Section 5 — Unit Tests

44 tests are organized into 7 groups, run with a shared `run_test(name, condition, fail_msg)` framework that prints `PASS` or `FAIL` for each case.

| Group | Tests | What it checks |
|---|---|---|
| Basic Correctness | 7 | Fills correct cells, walls and pre-filled cells untouched, both algorithms produce identical results |
| Edge Cases | 10 | 1×1 grid, start on wall, `target == fill` bug, already-filled grid |
| Connectivity | 8 | Wall barriers, L-shaped corridors, corner starting points |
| Multi-color Grids | 7 | Only `target_color` cells replaced, other colors untouched |
| Performance | 6 | BFS handles large grids safely, both complete in under 1 second |
| Time Complexity | 2 | Time scales linearly as N grows (not O(N²)) |
| Space Complexity | 4 | Stack depth (recursive) and queue peak size (BFS) both grow linearly |

### Known bug documented in tests:
When `target_color == fill_color`:
- **Recursive** → infinite recursion → `RecursionError` crash
- **BFS** → infinite loop → program hangs

Fix: add an early return guard `if target_color == fill_color: return`

### Final result: **41 passed | 3 failed | 44 total**
The 3 failures are all **known, documented bugs** (the `target == fill` cases above and a memory comparison edge case), not unexpected failures.

---

## Section 6 — Complexity Analysis

### Theoretical complexity

Let **N = total number of cells** (rows × cols).

| Algorithm | Time | Space |
|---|---|---|
| Recursive Flood Fill | O(N) | O(N) call stack |
| BFS Flood Fill | O(N) | O(N) queue |

Both visit each cell **at most once** — once painted, a cell no longer matches `target_color` and is never revisited.

### Why recursive uses more memory in practice:
Although both are O(N) space theoretically, the constant factor differs:
- **Recursive:** each stack frame stores the full function context — local variables, return address, Python frame overhead (~hundreds of bytes per frame)
- **BFS:** queue stores only `(row, col)` tuples — 2 integers per cell (~56 bytes per entry)

### How we verify O(N):
- **Time:** double the grid side length (N quadruples) → measure time also roughly quadruples, not 16× (which would indicate O(N²))
- **Space recursive:** instrument `flood_fill` to track actual call-stack depth — confirm it grows proportionally with N
- **Space BFS:** track peak queue length during BFS — confirm it grows proportionally with N
- **Memory:** use Python's `tracemalloc` to measure actual peak bytes allocated

---

## Section 7 — Pygame Visualizer

### What it does:
An interactive GUI where you can draw walls, place start/end points, and watch BFS explore the grid and trace the shortest path in real time.

### Architecture:
```
┌─────────────────────────────────────┐
│  Event Layer   (keyboard & mouse)   │  ← user input
├─────────────────────────────────────┤
│  Logic Layer   (BFS generator)      │  ← algorithm step-by-step
├─────────────────────────────────────┤
│  Render Layer  (draw_grid + panel)  │  ← visual output
└─────────────────────────────────────┘
```

### Key design: Python Generator for smooth animation
Running BFS all at once would freeze the display. Instead, `bfs_path_generator` uses Python's `yield` to emit one step at a time:
```python
yield ("visit", r, c)    # BFS discovered a new cell
yield ("path", r, c)     # tracing the shortest path
yield ("no_path",)       # search exhausted, no route found
```
The main loop calls `next(bfs_generator)` once every `BFS_DELAY` milliseconds — smooth animation without blocking the UI.

### Controls:

| Key | Action |
|---|---|
| `W` | Draw wall mode |
| `E` | Erase mode |
| `S` | Set start cell (green) |
| `D` | Set end cell (red) |
| `SPACE` | Run BFS pathfinding |
| `R` | Reset grid |
| `ESC` | Quit |

### Color legend:

| Color | Meaning |
|---|---|
| 🟢 Green | Start cell |
| 🔴 Red | End cell |
| ⬛ Black | Wall |
| 🔵 Blue | Visited during BFS |
| 🟡 Yellow | Shortest path |

---

## Requirements

```bash
pip install pygame
```

Python 3.x (developed on Python 3.13.9 with Anaconda)

---

## How to Run

1. Open `phase2_Pygame.ipynb` in Jupyter Notebook or JupyterLab
2. Run all cells from top to bottom
3. The final cell launches the Pygame visualizer in a separate window

> ⚠️ Pygame opens a native OS window — does not work in JupyterHub or Google Colab. Run locally.

---

## Conclusion

| | Recursive | BFS |
|---|---|---|
| Correctness | ✅ Small grids | ✅ All sizes |
| Time complexity | O(N) | O(N) |
| Space complexity | O(N) — heavier per cell | O(N) — lighter per cell |
| Stack overflow risk | ⚠️ Yes | ✅ No |
| Shortest path | ❌ No | ✅ Yes |
| Code simplicity | ✅ Very simple | Slightly more verbose |

**Key takeaway:** Both algorithms are O(N), but BFS is safer, more memory-efficient in practice, and capable of shortest-path reconstruction — making it the better choice for production use and pathfinding applications.
