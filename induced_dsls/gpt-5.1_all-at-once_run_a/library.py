from __future__ import annotations

WIDTH = 18
HEIGHT = 10
COLORS = ["white", "black", "yellow", "green", "red", "blue", "purple", "orange"]
DIRECTIONS = ["up", "down", "up_right", "down_left", "up_left", "down_right"]

_game_context = []


def _active_game():
    if not _game_context:
        raise RuntimeError(
            "No active Game. Use 'with Game() as g:' or pass game= explicitly"
        )
    return _game_context[-1]


class Game:
    def __init__(self, width: int = WIDTH, height: int = HEIGHT):
        self.start(width, height)

    def __enter__(self):
        _game_context.append(self)
        return self

    def __exit__(self, exc_type, exc, tb):
        _game_context.pop()
        return False

    def start(self, width: int = WIDTH, height: int = HEIGHT):
        self.width = width
        self.height = height
        self.board_state = [0] * (width * height)
        return self

    def plot(self, gold_boards=None, file_name=None, show=True):
        import hexagen.plot_board as pb

        boards = [self.board_state]
        titles = [""]

        if gold_boards is not None:
            gold_board = (
                gold_boards if not isinstance(gold_boards[0], list) else gold_boards[-1]
            )
            diff = [0 if x == y else 1 for x, y in zip(self.board_state, gold_board)]
            boards = [self.board_state, gold_board, diff]
            titles = ["code generated", "gold", "difference"]

        fig = pb.plot_boards(
            boards=boards,
            fig_size=[7, 5],
            height=self.height,
            width=self.width,
            max_in_row=3,
            h_pad=2,
            titles=titles,
            show=show,
        )
        if file_name is not None:
            fig.savefig(file_name)
        return fig


    def transform_pattern(
        self,
        tiles: list[Tile],
        anchor: Tile | tuple[int, int] | None = None,
        translation: tuple[int, int] = (0, 0),
        mirror_axis: str | None = None,
        rotate_steps: int = 0,
    ) -> list[Tile]:
        """Apply rotation, mirroring, and translation to a motif defined by `tiles`.

        Operations are applied in the following order:

            1. Rotate around `anchor` by `rotate_steps * 60°` (clockwise).
            2. Mirror across the specified `mirror_axis` through `anchor`
               ('vertical', 'horizontal', 'diag_up', or 'diag_down'), if any.
            3. Translate by `translation = (dr, dc)` in (row, column) space.

        All returned tiles are clipped to the board.

        Args:
            tiles: List of Tile objects describing the source pattern.
            anchor: Tile or (row, column) tuple used as the rotation and
                mirroring center. If None, the first tile in `tiles` is used.
            translation: (dr, dc) to add to row and column after rotation
                and mirroring.
            mirror_axis: One of 'vertical', 'horizontal', 'diag_up',
                'diag_down', or None for no mirroring.
            rotate_steps: Integer number of 60° clockwise rotation steps
                around `anchor`. Negative values rotate counter‑clockwise.

        Returns:
            A list of Tile objects representing the transformed pattern,
            with duplicates removed and clipped to the board.

        Raises:
            TypeError: If `tiles` is not a list of Tile objects, if `anchor`
                is not a Tile or (row, column) tuple, if `translation` is
                not a 2‑tuple of ints, or if `rotate_steps` is not an int.
            ValueError: If `mirror_axis` is invalid, if any Tile belongs to
                a different Game instance, or if `anchor` is None and
                `tiles` is empty.

        Examples:
            Pure translation of a two‑tile vertical pattern:

            >>> from hexagen import Game, Tile
            >>> g = Game(5, 5)
            >>> t1 = Tile(2, 2, g)
            >>> t2 = Tile(3, 2, g)
            >>> moved = g.transform_pattern([t1, t2], translation=(1, 1))
            >>> sorted((t.row, t.column) for t in moved)
            [(3, 3), (4, 3)]
        """

        if not isinstance(tiles, list):
            raise TypeError(
                f"tiles must be a list of Tile objects, got {type(tiles).__name__} instead."
            )
        if not tiles:
            # Nothing to transform.
            return []

        for t in tiles:
            if not isinstance(t, Tile):
                raise TypeError(
                    "All elements of tiles must be Tile instances. "
                    f"Found element {t!r} of type {type(t).__name__}."
                )
            if t.game is not self:
                raise ValueError(
                    "All tiles must belong to the same Game instance that "
                    "transform_pattern is called on."
                )

        if anchor is None:
            anchor_row, anchor_col = tiles[0].row, tiles[0].column
        else:
            if isinstance(anchor, Tile):
                if anchor.game is not self:
                    raise ValueError(
                        "anchor tile belongs to a different Game instance. "
                        "Pass a Tile from this Game or a (row, column) tuple."
                    )
                anchor_row, anchor_col = anchor.row, anchor.column
            else:
                try:
                    anchor_row, anchor_col = anchor  # type: ignore[misc]
                except (TypeError, ValueError):
                    raise TypeError(
                        "anchor must be a Tile, a (row, column) tuple, or None. "
                        f"Got {type(anchor).__name__} instead."
                    ) from None
                if not (isinstance(anchor_row, int) and isinstance(anchor_col, int)):
                    raise TypeError(
                        "anchor coordinates must be integers (row, column); "
                        f"got ({anchor_row!r}, {anchor_col!r})."
                    )

        if not (
            isinstance(translation, tuple)
            and len(translation) == 2
            and isinstance(translation[0], int)
            and isinstance(translation[1], int)
        ):
            raise TypeError(
                "translation must be a tuple of two integers (dr, dc). "
                f"Got {translation!r}."
            )
        dr, dc = translation

        valid_axes = {None, "vertical", "horizontal", "diag_up", "diag_down"}
        if mirror_axis not in valid_axes:
            raise ValueError(
                "mirror_axis must be one of "
                "{None, 'vertical', 'horizontal', 'diag_up', 'diag_down'}, "
                f"got {mirror_axis!r}."
            )

        if not isinstance(rotate_steps, int):
            raise TypeError(
                f"rotate_steps must be an int, got {type(rotate_steps).__name__} instead."
            )

        def _offset_to_cube(row: int, col: int) -> tuple[int, int, int]:
            q = col - 1
            r = row - 1
            x = q
            z = r - (q - (q & 1)) // 2
            y = -x - z
            return x, y, z

        def _cube_to_offset(x: int, y: int, z: int) -> tuple[int, int]:
            q = x
            r = z + (q - (q & 1)) // 2
            return r + 1, q + 1

        def _cube_rotate_cw(x: int, y: int, z: int, steps: int) -> tuple[int, int, int]:
            steps %= 6
            for _ in range(steps):
                x, y, z = -z, -x, -y
            return x, y, z

        # Anchor in cube coordinates.
        ax, ay, az = _offset_to_cube(anchor_row, anchor_col)

        result_coords: set[tuple[int, int]] = set()

        for tile in tiles:
            row, col = tile.row, tile.column
            x, y, z = _offset_to_cube(row, col)

            # Rotate around anchor in cube space.
            dx, dy, dz = x - ax, y - ay, z - az
            rdx, rdy, rdz = _cube_rotate_cw(dx, dy, dz, rotate_steps)
            rx, ry, rz = ax + rdx, ay + rdy, az + rdz
            rrow, rcol = _cube_to_offset(rx, ry, rz)

            # Mirror around anchor in offset (row, col) space.
            drow = rrow - anchor_row
            dcol = rcol - anchor_col

            if mirror_axis == "vertical":
                dcol = -dcol
            elif mirror_axis == "horizontal":
                drow = -drow
            elif mirror_axis == "diag_up":
                # Approximate reflection across a rising diagonal through the anchor.
                drow, dcol = -dcol, -drow
            elif mirror_axis == "diag_down":
                # Approximate reflection across a falling diagonal through the anchor.
                drow, dcol = dcol, drow

            mrow = anchor_row + drow
            mcol = anchor_col + dcol

            # Apply final translation.
            final_row = mrow + dr
            final_col = mcol + dc

            if 1 <= final_row <= self.height and 1 <= final_col <= self.width:
                result_coords.add((final_row, final_col))

        return [Tile(r, c, game=self) for (r, c) in sorted(result_coords)]


    def fill_region(
        self,
        seed: Tile | tuple[int, int],
        color: str,
        boundary_colors: set[str] | None = None,
    ) -> list[Tile]:
        """Flood‑fill a region starting from `seed` and recolor it.

        If `boundary_colors` is None, this behaves like a standard paint
        bucket: it recolors all tiles hex‑adjacent to `seed` that share the
        same original color as `seed`.

        If `boundary_colors` is a set of color names, the flood stops when
        it encounters any tile whose color is in `boundary_colors`. Those
        boundary tiles are not recolored.

        Args:
            seed: Starting tile as a Tile or (row, column) tuple. Must be
                on the board.
            color: Target color name (must be in COLORS) or an integer
                color index.
            boundary_colors: Optional set of color names that act as
                boundaries (not filled and not crossed). If None, the
                contiguous region of the seed's original color is filled.

        Returns:
            A list of Tile objects that were recolored.

        Raises:
            TypeError: If `seed` is not a Tile or (row, column) tuple, if
                `color` is not a string or int, or if `boundary_colors`
                is not a set of strings (or None).
            ValueError: If `seed` is off the board, if any color name is
                unknown, if color index is out of range, or if a Tile
                belongs to a different Game instance.

        Examples:
            Basic region fill (no explicit boundary):

            >>> from hexagen import Game, Tile
            >>> g = Game(4, 3)
            >>> Tile(2, 2, g).draw("red")
            >>> Tile(2, 3, g).draw("red")
            >>> filled = g.fill_region((2, 2), "blue")
            >>> sorted((t.row, t.column) for t in filled)
            [(2, 2), (2, 3)]
            >>> {Tile(2, 2, g).color, Tile(2, 3, g).color}
            {'blue'}

            With an explicit black boundary around the center:

            >>> g = Game(3, 3)
            >>> boundary = [(1, c) for c in range(1, 4)] + \\
            ...            [(3, c) for c in range(1, 4)] + \\
            ...            [(2, 1), (2, 3)]
            >>> for r, c in boundary:
            ...     Tile(r, c, g).draw("black")
            >>> filled = g.fill_region((2, 2), "yellow", boundary_colors={"black"})
            >>> sorted((t.row, t.column) for t in filled)
            [(2, 2)]
            >>> Tile(2, 2, g).color
            'yellow'
        """

        from collections import deque

        def _normalize_tile(tile, name: str) -> tuple[int, int]:
            if isinstance(tile, Tile):
                if tile.game is not self:
                    raise ValueError(
                        f"{name} tile belongs to a different Game instance. "
                        "Pass a Tile created with this Game or a (row, column) tuple."
                    )
                return tile.row, tile.column
            try:
                row, col = tile  # type: ignore[misc]
            except (TypeError, ValueError):
                raise TypeError(
                    f"{name} must be a Tile or a (row, column) tuple of integers, "
                    f"got {type(tile).__name__} instead."
                ) from None
            if not (isinstance(row, int) and isinstance(col, int)):
                raise TypeError(
                    f"{name} coordinates must be integers (row, column); "
                    f"got ({row!r}, {col!r})."
                )
            return row, col

        def _offset_to_cube(row: int, col: int) -> tuple[int, int, int]:
            q = col - 1
            r = row - 1
            x = q
            z = r - (q - (q & 1)) // 2
            y = -x - z
            return x, y, z

        def _cube_to_offset(x: int, y: int, z: int) -> tuple[int, int]:
            q = x
            r = z + (q - (q & 1)) // 2
            return r + 1, q + 1

        dir_vectors: tuple[tuple[int, int, int], ...] = (
            (0, 1, -1),    # up
            (0, -1, 1),    # down
            (1, 0, -1),    # up_right
            (-1, 0, 1),    # down_left
            (-1, 1, 0),    # up_left
            (1, -1, 0),    # down_right
        )

        sr, sc = _normalize_tile(seed, "seed")
        if not (1 <= sr <= self.height and 1 <= sc <= self.width):
            raise ValueError(
                f"seed {seed!r} is off the board (rows 1..{self.height}, "
                f"columns 1..{self.width}). Use an on‑board seed tile."
            )

        # Normalize color to a color id.
        if isinstance(color, str):
            if color not in COLORS:
                raise ValueError(
                    f"color {color!r} is not a valid color name. "
                    f"Valid colors are: {COLORS!r}."
                )
            new_color_id = COLORS.index(color)
        elif isinstance(color, int):
            if not (0 <= color < len(COLORS)):
                raise ValueError(
                    f"color index {color} is out of range. "
                    f"Use an index between 0 and {len(COLORS) - 1}."
                )
            new_color_id = int(color)
        else:
            raise TypeError(
                f"color must be a color name (str) or an integer index, "
                f"got {type(color).__name__} instead."
            )

        boundary_ids: set[int] | None
        if boundary_colors is None:
            boundary_ids = None
        else:
            if not isinstance(boundary_colors, set):
                raise TypeError(
                    "boundary_colors must be a set of color names or None. "
                    f"Got {type(boundary_colors).__name__} instead."
                )
            boundary_ids = set()
            for bc in boundary_colors:
                if not isinstance(bc, str):
                    raise TypeError(
                        "All entries in boundary_colors must be strings naming colors. "
                        f"Got element {bc!r} of type {type(bc).__name__}."
                    )
                if bc not in COLORS:
                    raise ValueError(
                        f"Boundary color {bc!r} is not valid. "
                        f"Valid colors are: {COLORS!r}."
                    )
                boundary_ids.add(COLORS.index(bc))

        width = self.width
        height = self.height

        def _index(row: int, col: int) -> int:
            return (row - 1) * width + (col - 1)

        board = self.board_state
        seed_idx = _index(sr, sc)
        seed_color_id = board[seed_idx]

        # If the seed itself is a boundary tile, nothing gets filled.
        if boundary_ids is not None and seed_color_id in boundary_ids:
            return []

        visited: set[tuple[int, int]] = set()
        q = deque()
        q.append((sr, sc))
        visited.add((sr, sc))

        filled_coords: list[tuple[int, int]] = []

        while q:
            row, col = q.popleft()
            idx = _index(row, col)
            board[idx] = new_color_id
            filled_coords.append((row, col))

            cx, cy, cz = _offset_to_cube(row, col)
            for dx, dy, dz in dir_vectors:
                nx = cx + dx
                ny = cy + dy
                nz = cz + dz
                nr, nc = _cube_to_offset(nx, ny, nz)
                if not (1 <= nr <= height and 1 <= nc <= width):
                    continue
                if (nr, nc) in visited:
                    continue
                n_idx = _index(nr, nc)
                n_color_id = board[n_idx]
                if boundary_ids is None:
                    # Standard flood fill: stay within the original seed color.
                    if n_color_id != seed_color_id:
                        continue
                else:
                    # Boundary mode: stop at boundary colors, otherwise traverse freely.
                    if n_color_id in boundary_ids:
                        continue
                visited.add((nr, nc))
                q.append((nr, nc))

        return [Tile(r, c, game=self) for (r, c) in filled_coords]


    def hex_triangle(
        self,
        apex: Tile | tuple[int, int],
        orientation: str,
        side: int,
        fill: bool = True,
    ) -> list[Tile]:
        """Return an equilateral hex‑grid triangle with the given apex and side.

        The triangle has all three sides of hex distance `side-1`, aligned to
        the hex grid axes. The apex is at the given tile, and the triangle
        points in `orientation`.

        Orientations:
            - 'up', 'down', 'up_left', 'up_right', 'down_left', 'down_right'

        Args:
            apex: Apex tile as a Tile or (row, column) tuple.
            orientation: Direction the apex points in, one of the six
                orientation strings above.
            side: Positive integer edge length in tiles.
            fill: If True (default), return all tiles inside the triangle;
                if False, return only the outline (edges).

        Returns:
            A list of Tile objects forming the triangle (filled or outline),
            clipped to the board.

        Raises:
            TypeError: If `apex` is not a Tile or (row, column) tuple, or
                if `side` is not an int, or if `fill` is not a bool.
            ValueError: If `side` <= 0, `orientation` is invalid, or a Tile
                belongs to a different Game instance.

        Examples:
            >>> from hexagen import Game
            >>> g = Game(5, 5)
            >>> tri = g.hex_triangle((2, 2), 'up', side=2, fill=True)
            >>> sorted((t.row, t.column) for t in tri)
            [(2, 2), (3, 1), (3, 3)]
        """

        def _normalize_tile(tile, name: str) -> tuple[int, int]:
            if isinstance(tile, Tile):
                if tile.game is not self:
                    raise ValueError(
                        f"{name} tile belongs to a different Game instance. "
                        "Pass a Tile created with this Game or a (row, column) tuple."
                    )
                return tile.row, tile.column
            try:
                row, col = tile  # type: ignore[misc]
            except (TypeError, ValueError):
                raise TypeError(
                    f"{name} must be a Tile or a (row, column) tuple of integers, "
                    f"got {type(tile).__name__} instead."
                ) from None
            if not (isinstance(row, int) and isinstance(col, int)):
                raise TypeError(
                    f"{name} coordinates must be integers (row, column); "
                    f"got ({row!r}, {col!r})."
                )
            return row, col

        if not isinstance(side, int):
            raise TypeError(
                f"side must be a positive integer, got {type(side).__name__} instead."
            )
        if side <= 0:
            raise ValueError(
                f"side must be a positive integer, got {side}. "
                "Use side >= 1 when constructing hex triangles."
            )
        if not isinstance(fill, bool):
            raise TypeError(
                f"fill must be a bool, got {type(fill).__name__} instead."
            )

        orientation_order = [
            "up",
            "up_right",
            "down_right",
            "down",
            "down_left",
            "up_left",
        ]
        if orientation not in orientation_order:
            raise ValueError(
                f"orientation must be one of {orientation_order!r}, "
                f"got {orientation!r}. Use a valid hex triangle orientation."
            )

        def _offset_to_cube(row: int, col: int) -> tuple[int, int, int]:
            q = col - 1
            r = row - 1
            x = q
            z = r - (q - (q & 1)) // 2
            y = -x - z
            return x, y, z

        def _cube_to_offset(x: int, y: int, z: int) -> tuple[int, int]:
            q = x
            r = z + (q - (q & 1)) // 2
            return r + 1, q + 1

        def _cube_rotate_cw(x: int, y: int, z: int, steps: int) -> tuple[int, int, int]:
            steps %= 6
            for _ in range(steps):
                x, y, z = -z, -x, -y
            return x, y, z

        # Base direction vectors in cube coordinates.
        dir_vectors: dict[str, tuple[int, int, int]] = {
            "up": (0, 1, -1),
            "down": (0, -1, 1),
            "up_right": (1, 0, -1),
            "down_left": (-1, 0, 1),
            "up_left": (-1, 1, 0),
            "down_right": (1, -1, 0),
        }

        dl = dir_vectors["down_left"]
        dr = dir_vectors["down_right"]

        ar, ac = _normalize_tile(apex, "apex")
        ax, ay, az = _offset_to_cube(ar, ac)

        base_cubes: set[tuple[int, int, int]] = set()

        if fill:
            # Filled "up" triangle: apex + a*DL + b*DR, with a, b >= 0 and a + b <= side-1.
            for a in range(side):
                for b in range(side - a):
                    x = ax + a * dl[0] + b * dr[0]
                    y = ay + a * dl[1] + b * dr[1]
                    z = az + a * dl[2] + b * dr[2]
                    base_cubes.add((x, y, z))
        else:
            # Outline only: three edges of the "up" triangle.
            # Edge 1: apex -> apex + (side-1)*DL
            for i in range(side):
                x = ax + i * dl[0]
                y = ay + i * dl[1]
                z = az + i * dl[2]
                base_cubes.add((x, y, z))
            # Edge 2: apex -> apex + (side-1)*DR
            for i in range(side):
                x = ax + i * dr[0]
                y = ay + i * dr[1]
                z = az + i * dr[2]
                base_cubes.add((x, y, z))
            # Edge 3: between the two base vertices.
            for i in range(side):
                a = i
                b = (side - 1) - i
                x = ax + a * dl[0] + b * dr[0]
                y = ay + a * dl[1] + b * dr[1]
                z = az + a * dl[2] + b * dr[2]
                base_cubes.add((x, y, z))

        # Rotate the base "up" triangle to the requested orientation around the apex.
        steps = orientation_order.index(orientation)
        tiles_coords: set[tuple[int, int]] = set()

        for (x, y, z) in base_cubes:
            # Translate to apex-centered, rotate, translate back.
            dx, dy, dz = x - ax, y - ay, z - az
            rdx, rdy, rdz = _cube_rotate_cw(dx, dy, dz, steps)
            rx, ry, rz = ax + rdx, ay + rdy, az + rdz
            row, col = _cube_to_offset(rx, ry, rz)
            if 1 <= row <= self.height and 1 <= col <= self.width:
                tiles_coords.add((row, col))

        return [Tile(r, c, game=self) for (r, c) in sorted(tiles_coords)]


    def hex_ray(
        self,
        start: Tile | tuple[int, int],
        direction: str,
        length: int | None = None,
    ) -> list[Tile]:
        """Return tiles on a ray from `start` in the given hex `direction`.

        The starting tile is included as the first element. If `length` is
        given, at most `length` tiles are returned (including `start`).
        If `length` is None, the ray continues until it leaves the board.

        Args:
            start: Starting tile as a Tile or (row, column) tuple. Must be
                on the board.
            direction: One of DIRECTIONS: 'up', 'down', 'up_right',
                'down_left', 'up_left', 'down_right'.
            length: Maximum number of tiles to return (including `start`),
                or None to extend to the board edge.

        Returns:
            A list of Tile objects along the ray, starting at `start` and
            stepping in `direction`.

        Raises:
            TypeError: If `start` is not a Tile or (row, column) tuple, or
                if `length` is not an int or None.
            ValueError: If `start` is off the board, `direction` is invalid,
                or `length` is negative, or a Tile belongs to a different
                Game instance.

        Examples:
            >>> from hexagen import Game
            >>> g = Game(5, 5)
            >>> ray = g.hex_ray((2, 2), 'down', length=3)
            >>> [(t.row, t.column) for t in ray]
            [(2, 2), (3, 2), (4, 2)]
        """

        def _normalize_tile(tile, name: str) -> tuple[int, int]:
            if isinstance(tile, Tile):
                if tile.game is not self:
                    raise ValueError(
                        f"{name} tile belongs to a different Game instance. "
                        "Pass a Tile created with this Game or a (row, column) tuple."
                    )
                return tile.row, tile.column
            try:
                row, col = tile  # type: ignore[misc]
            except (TypeError, ValueError):
                raise TypeError(
                    f"{name} must be a Tile or a (row, column) tuple of integers, "
                    f"got {type(tile).__name__} instead."
                ) from None
            if not (isinstance(row, int) and isinstance(col, int)):
                raise TypeError(
                    f"{name} coordinates must be integers (row, column); "
                    f"got ({row!r}, {col!r})."
                )
            return row, col

        if direction not in DIRECTIONS:
            raise ValueError(
                f"direction must be one of {DIRECTIONS!r}, got {direction!r}. "
                "Use a valid hex direction string."
            )

        if length is not None:
            if not isinstance(length, int):
                raise TypeError(
                    f"length must be an int or None, got {type(length).__name__} instead."
                )
            if length < 0:
                raise ValueError(
                    f"length must be >= 0 or None, got {length}. "
                    "Use length=0 for an empty ray or a positive length."
                )

        def _offset_to_cube(row: int, col: int) -> tuple[int, int, int]:
            q = col - 1
            r = row - 1
            x = q
            z = r - (q - (q & 1)) // 2
            y = -x - z
            return x, y, z

        def _cube_to_offset(x: int, y: int, z: int) -> tuple[int, int]:
            q = x
            r = z + (q - (q & 1)) // 2
            return r + 1, q + 1

        dir_vectors: dict[str, tuple[int, int, int]] = {
            "up": (0, 1, -1),
            "down": (0, -1, 1),
            "up_right": (1, 0, -1),
            "down_left": (-1, 0, 1),
            "up_left": (-1, 1, 0),
            "down_right": (1, -1, 0),
        }

        sr, sc = _normalize_tile(start, "start")
        if not (1 <= sr <= self.height and 1 <= sc <= self.width):
            raise ValueError(
                f"start tile {start!r} is off the board (rows 1..{self.height}, "
                f"columns 1..{self.width}). Use an on‑board starting position."
            )

        sx, sy, sz = _offset_to_cube(sr, sc)
        dx, dy, dz = dir_vectors[direction]

        result: list[Tile] = []
        steps = length if length is not None else float("inf")
        i = 0
        while i < steps:
            x = sx + dx * i
            y = sy + dy * i
            z = sz + dz * i
            row, col = _cube_to_offset(x, y, z)
            if not (1 <= row <= self.height and 1 <= col <= self.width):
                break
            result.append(Tile(row, col, game=self))
            i += 1

        return result


    def hex_line(self, start: Tile | tuple[int, int], end: Tile | tuple[int, int]) -> list[Tile]:
        """Return the straight hex‑grid line segment from `start` to `end`.

        The line follows the hex lattice using hex interpolation and rounding,
        and includes both endpoints. Tiles outside the board are silently
        dropped so the returned list always contains only on‑board tiles.

        Args:
            start: Start tile as a Tile or (row, column) tuple.
            end: End tile as a Tile or (row, column) tuple.

        Returns:
            A list of Tile objects forming the straight hex‑grid segment from
            `start` to `end`, inclusive, clipped to the board.

        Raises:
            TypeError: If `start` or `end` is not a Tile or (row, column) tuple.
            ValueError: If a Tile belongs to a different Game instance.

        Examples:
            >>> from hexagen import Game
            >>> g = Game(5, 5)
            >>> line = g.hex_line((1, 1), (3, 1))
            >>> [(t.row, t.column) for t in line]
            [(1, 1), (2, 1), (3, 1)]
        """

        def _normalize_tile(tile, name: str) -> tuple[int, int]:
            if isinstance(tile, Tile):
                if tile.game is not self:
                    raise ValueError(
                        f"{name} tile belongs to a different Game instance. "
                        "Pass a Tile created with this Game or a (row, column) tuple."
                    )
                return tile.row, tile.column
            try:
                row, col = tile  # type: ignore[misc]
            except (TypeError, ValueError):
                raise TypeError(
                    f"{name} must be a Tile or a (row, column) tuple of integers, "
                    f"got {type(tile).__name__} instead."
                ) from None
            if not (isinstance(row, int) and isinstance(col, int)):
                raise TypeError(
                    f"{name} coordinates must be integers (row, column); "
                    f"got ({row!r}, {col!r})."
                )
            return row, col

        def _offset_to_cube(row: int, col: int) -> tuple[float, float, float]:
            q = col - 1
            r = row - 1
            x = q
            z = r - (q - (q & 1)) // 2
            y = -x - z
            return float(x), float(y), float(z)

        def _cube_to_offset(x: float, y: float, z: float) -> tuple[int, int]:
            q = int(round(x))
            z_int = int(round(z))
            r = z_int + (q - (q & 1)) // 2
            return r + 1, q + 1

        def _cube_round(x: float, y: float, z: float) -> tuple[float, float, float]:
            rx = round(x)
            ry = round(y)
            rz = round(z)
            dx = abs(rx - x)
            dy = abs(ry - y)
            dz = abs(rz - z)
            if dx > dy and dx > dz:
                rx = -ry - rz
            elif dy > dz:
                ry = -rx - rz
            else:
                rz = -rx - ry
            return rx, ry, rz

        sr, sc = _normalize_tile(start, "start")
        er, ec = _normalize_tile(end, "end")

        sx, sy, sz = _offset_to_cube(sr, sc)
        ex, ey, ez = _offset_to_cube(er, ec)

        n = int((abs(sx - ex) + abs(sy - ey) + abs(sz - ez)) // 2)
        if n == 0:
            if 1 <= sr <= self.height and 1 <= sc <= self.width:
                return [Tile(sr, sc, game=self)]
            return []

        result: list[Tile] = []
        last_rc: tuple[int, int] | None = None
        for i in range(n + 1):
            t = i / n
            x = sx + (ex - sx) * t
            y = sy + (ey - sy) * t
            z = sz + (ez - sz) * t
            rx, ry, rz = _cube_round(x, y, z)
            row, col = _cube_to_offset(rx, ry, rz)
            if 1 <= row <= self.height and 1 <= col <= self.width:
                if last_rc != (row, col):
                    result.append(Tile(row, col, game=self))
                    last_rc = (row, col)
        return result


    def hex_ring(self, center: Tile | tuple[int, int], radius: int) -> list[Tile]:
        """Return all tiles at exactly hex distance `radius` from `center`.

        The ring is defined in hex distance (via DIRECTIONS) and clipped
        to the current board.

        Args:
            center: Center tile as a Tile or (row, column) tuple.
            radius: Non‑negative integer hex radius.

        Returns:
            A list of Tile objects at distance exactly `radius` from `center`,
            ordered in row‑major order and clipped to the board.

        Raises:
            TypeError: If `center` is not a Tile or (row, column) tuple, or
                if `radius` is not an integer.
            ValueError: If `radius` is negative, or if a Tile belongs to a
                different Game instance.

        Examples:
            >>> from hexagen import Game
            >>> g = Game(5, 5)
            >>> ring = g.hex_ring((3, 3), 1)
            >>> sorted((t.row, t.column) for t in ring)
            [(2, 2), (2, 3), (2, 4), (3, 2), (3, 4), (4, 3)]
            >>> g.hex_ring((3, 3), 0)[0].row, g.hex_ring((3, 3), 0)[0].column
            (3, 3)
        """

        if not isinstance(radius, int):
            raise TypeError(
                f"radius must be an integer >= 0, got {type(radius).__name__} instead."
            )
        if radius < 0:
            raise ValueError(
                f"radius must be non‑negative, got {radius}. "
                "Use radius >= 0 when requesting hex rings."
            )

        def _normalize_tile(tile, name: str) -> tuple[int, int]:
            if isinstance(tile, Tile):
                if tile.game is not self:
                    raise ValueError(
                        f"{name} tile belongs to a different Game instance. "
                        "Pass a Tile created with this Game or a (row, column) tuple."
                    )
                return tile.row, tile.column
            try:
                row, col = tile  # type: ignore[misc]
            except (TypeError, ValueError):
                raise TypeError(
                    f"{name} must be a Tile or a (row, column) tuple of integers, "
                    f"got {type(tile).__name__} instead."
                ) from None
            if not (isinstance(row, int) and isinstance(col, int)):
                raise TypeError(
                    f"{name} coordinates must be integers (row, column); "
                    f"got ({row!r}, {col!r})."
                )
            return row, col

        cr, cc = _normalize_tile(center, "center")

        tiles: list[Tile] = []
        for row in range(1, self.height + 1):
            for col in range(1, self.width + 1):
                if self.hex_distance((row, col), (cr, cc)) == radius:
                    tiles.append(Tile(row, col, game=self))
        return tiles


    def hex_distance(self, a: Tile | tuple[int, int], b: Tile | tuple[int, int]) -> int:
        """Return the hex‑grid distance between two tiles.

        The distance is the minimum number of hex steps (using DIRECTIONS)
        needed to go from `a` to `b`. Works even if the coordinates are
        outside the current board; the board size is ignored.

        Args:
            a: Start tile as a Tile or a (row, column) integer tuple.
            b: End tile as a Tile or a (row, column) integer tuple.

        Returns:
            The non‑negative integer hex distance between `a` and `b`.

        Raises:
            TypeError: If `a` or `b` is not a Tile or a (row, column) tuple
                of integers.
            ValueError: If a Tile belongs to a different Game instance.

        Examples:
            >>> from hexagen import Game, Tile
            >>> g = Game(5, 5)
            >>> g.hex_distance((1, 1), (3, 1))
            2
            >>> t1 = Tile(2, 2, g)
            >>> t2 = Tile(4, 3, g)
            >>> g.hex_distance(t1, t2) == g.hex_distance(t2, t1)
            True
        """

        def _normalize_tile(tile, name: str) -> tuple[int, int]:
            if isinstance(tile, Tile):
                if tile.game is not self:
                    raise ValueError(
                        f"{name} tile belongs to a different Game instance. "
                        "Pass a Tile created with this Game or a (row, column) tuple."
                    )
                return tile.row, tile.column
            try:
                row, col = tile  # type: ignore[misc]
            except (TypeError, ValueError):
                raise TypeError(
                    f"{name} must be a Tile or a (row, column) tuple of integers, "
                    f"got {type(tile).__name__} instead."
                ) from None
            if not (isinstance(row, int) and isinstance(col, int)):
                raise TypeError(
                    f"{name} coordinates must be integers (row, column); "
                    f"got ({row!r}, {col!r})."
                )
            return row, col

        def _offset_to_cube(row: int, col: int) -> tuple[int, int, int]:
            # Odd-q vertical layout; rows/cols are 1-based here.
            q = col - 1
            r = row - 1
            x = q
            z = r - (q - (q & 1)) // 2
            y = -x - z
            return x, y, z

        ar, ac = _normalize_tile(a, "First position")
        br, bc = _normalize_tile(b, "Second position")

        ax, ay, az = _offset_to_cube(ar, ac)
        bx, by, bz = _offset_to_cube(br, bc)

        dx = abs(ax - bx)
        dy = abs(ay - by)
        dz = abs(az - bz)
        return (dx + dy + dz) // 2


class Tile:
    """Single addressable cell on the board (drawing-only)."""

    def __init__(self, row: int, column: int, game: Game = None):
        self.game = game or _active_game()

        if row < 0:
            row = self.game.height + 1 + row
        if column < 0:
            column = self.game.width + 1 + column

        self.row = row
        self.column = column

    def on_board(self) -> bool:
        return 1 <= self.row <= self.game.height and 1 <= self.column <= self.game.width

    @property
    def _lind(self):
        if not self.on_board():
            return None
        return (self.row - 1) * self.game.width + (self.column - 1)

    @property
    def color(self):
        lind = self._lind
        if lind is None:
            return None
        return COLORS[self.game.board_state[lind]]

    def draw(self, color):
        """Paint this tile. color can be a string in COLORS or an int color_id."""
        lind = self._lind
        if lind is None:
            return self

        color_id = COLORS.index(color) if isinstance(color, str) else int(color)
        self.game.board_state[lind] = color_id
        return self

    def __str__(self):
        return f"Tile(row={self.row}, column={self.column}, color={self.color})"
