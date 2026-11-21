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


    def fill_interior(
        self,
        seed: Tile | tuple[int, int],
        color: str,
        boundary_colors: set[str] | None = None,
    ) -> list[Tile]:
        """Flood-fill from ``seed`` until the board edge or a colored boundary.

        Starting at ``seed``, this performs a hex flood-fill over adjacent tiles,
        stopping when it reaches tiles whose colors are in ``boundary_colors``
        or the edge of the board.

        Args:
            seed: Starting tile, as a ``Tile`` or ``(row, column)`` tuple.
            color: The color to paint all reachable tiles.
            boundary_colors: Optional set of color names that act as barriers the
                fill will not cross.

        Returns:
            A list of ``Tile`` objects that were colored.

        Raises:
            TypeError: If ``seed`` is not a ``Tile`` or ``(row, column)`` tuple,
                or if ``boundary_colors`` is not a set or ``None``.
            ValueError: If ``seed`` is outside the board.
            ValueError: If ``seed``'s color is in ``boundary_colors``.
            ValueError: If ``seed`` is a ``Tile`` from a different ``Game``.
            ValueError: If ``color`` is not a valid color name.

        Examples:
            >>> g = Game(width=3, height=3)
            >>> # Draw a black frame around the center tile
            >>> for r in (1, 3):
            ...     for c in range(1, 4):
            ...         Tile(r, c, g).draw('black')
            >>> for r in range(1, 4):
            ...     for c in (1, 3):
            ...         Tile(r, c, g).draw('black')
            >>> filled = g.fill_interior((2, 2), color='red', boundary_colors={'black'})
            >>> sorted((t.row, t.column) for t in filled)
            [(2, 2)]
            >>> Tile(2, 2, g).color
            'red'
            >>> Tile(1, 1, g).color
            'black'
        """
        def _coerce_to_row_col(pos, name: str) -> tuple[int, int]:
            if isinstance(pos, Tile):
                if pos.game is not self:
                    raise ValueError(
                        f"{name} Tile belongs to a different Game instance; "
                        "use a Tile from this Game or pass a (row, column) tuple."
                    )
                return pos.row, pos.column
            if not (isinstance(pos, tuple) and len(pos) == 2):
                raise TypeError(
                    f"{name} must be a Tile or a (row, column) tuple, got {type(pos).__name__}."
                )
            row, col = pos
            if not isinstance(row, int) or not isinstance(col, int):
                raise TypeError(
                    f"{name} row and column must be integers, got {type(row).__name__} and {type(col).__name__}."
                )
            return row, col

        if boundary_colors is None:
            boundary_set: set[str] = set()
        else:
            if not isinstance(boundary_colors, set):
                raise TypeError(
                    f"boundary_colors must be a set of color names or None, got {type(boundary_colors).__name__}."
                )
            boundary_set = set(boundary_colors)

        if color not in COLORS:
            raise ValueError(
                f"color {color!r} is not a valid color; valid colors are {COLORS}."
            )

        row0, col0 = _coerce_to_row_col(seed, "seed")
        start_tile = Tile(row0, col0, self)
        if not start_tile.on_board():
            raise ValueError(
                f"seed {start_tile} is outside the board; "
                "fill_interior() requires the seed to be on the board."
            )

        if start_tile.color in boundary_set:
            raise ValueError(
                "The seed tile's color is in boundary_colors; start the fill on a "
                "tile that is not part of the boundary."
            )

        # Directions in axial (row, column) coordinates
        direction_steps: tuple[tuple[int, int], ...] = (
            (-1, 0),   # up
            (1, 0),    # down
            (-1, 1),   # up_right
            (1, -1),   # down_left
            (0, -1),   # up_left
            (0, 1),    # down_right
        )

        from collections import deque

        visited: set[tuple[int, int]] = set()
        q = deque()
        q.append((row0, col0))
        filled_tiles: list[Tile] = []

        while q:
            r, c = q.popleft()
            if (r, c) in visited:
                continue
            visited.add((r, c))

            t = Tile(r, c, self)
            if not t.on_board():
                continue
            if t.color in boundary_set:
                continue

            # Paint this tile
            t.draw(color)
            filled_tiles.append(t)

            for dr, dc in direction_steps:
                nr, nc = r + dr, c + dc
                if 1 <= nr <= self.height and 1 <= nc <= self.width:
                    if (nr, nc) not in visited:
                        neighbor = Tile(nr, nc, self)
                        if neighbor.color not in boundary_set:
                            q.append((nr, nc))

        return filled_tiles


    def copy_region(
        self,
        src_rows: range,
        src_columns: range,
        dest_offset: tuple[int, int],
        color_map: dict[str, str] | None = None,
        reflect: str = "none",
    ) -> list[Tile]:
        """Copy a rectangular region to a new location with optional reflection.

        The region defined by ``src_rows`` and ``src_columns`` is copied to a
        destination shifted by ``dest_offset`` (Δrow, Δcol). The region can
        optionally be reflected horizontally or vertically before the shift.

        Reflection is performed within the bounds of the source rectangle:

        * ``reflect='none'``: no reflection
        * ``reflect='vertical'``: mirror left-right within the region
        * ``reflect='horizontal'``: mirror top-bottom within the region

        Args:
            src_rows: Range of source rows.
            src_columns: Range of source columns.
            dest_offset: Tuple ``(Δrow, Δcol)`` added to each (possibly
                reflected) source coordinate to obtain the destination.
            color_map: Optional mapping ``{source_color: dest_color}`` applied
                during copying. Colors not in the map are copied unchanged.
            reflect: One of ``'none'``, ``'vertical'``, or ``'horizontal'``.

        Returns:
            A list of destination ``Tile`` objects that were written. Tiles that
            would fall outside the board are skipped.

        Raises:
            TypeError: If ``src_rows``/``src_columns`` are not ranges, or if
                ``dest_offset`` is not a 2-tuple of ints, or if ``color_map`` is
                not a dict.
            ValueError: If ``reflect`` is not one of the allowed values.
            ValueError: If ``color_map`` keys or values are not valid color names.

        Examples:
            >>> g = Game(width=4, height=2)
            >>> Tile(1, 1, g).draw('blue')
            Tile(row=1, column=1, color=blue)
            >>> Tile(2, 1, g).draw('red')
            Tile(row=2, column=1, color=red)
            >>> out = g.copy_region(src_rows=range(1, 3),
            ...                     src_columns=range(1, 2),
            ...                     dest_offset=(0, 2))
            >>> sorted((t.row, t.column) for t in out)
            [(1, 3), (2, 3)]
            >>> [Tile(r, c, g).color for r in range(1, 3) for c in range(1, 5)]
            ['blue', 'white', 'blue', 'white', 'red', 'white', 'red', 'white']
        """
        if not isinstance(src_rows, range):
            raise TypeError(f"src_rows must be a range, got {type(src_rows).__name__}.")
        if not isinstance(src_columns, range):
            raise TypeError(f"src_columns must be a range, got {type(src_columns).__name__}.")

        if not (isinstance(dest_offset, tuple) and len(dest_offset) == 2):
            raise TypeError(
                "dest_offset must be a (Δrow, Δcol) tuple of ints."
            )
        drow, dcol = dest_offset
        if not isinstance(drow, int) or not isinstance(dcol, int):
            raise TypeError(
                f"dest_offset elements must be ints, got {type(drow).__name__} and {type(dcol).__name__}."
            )

        if color_map is not None and not isinstance(color_map, dict):
            raise TypeError(f"color_map must be a dict or None, got {type(color_map).__name__}.")

        if color_map:
            for src, dst in color_map.items():
                if src not in COLORS:
                    raise ValueError(
                        f"color_map key {src!r} is not a valid color; valid colors are {COLORS}."
                    )
                if dst not in COLORS:
                    raise ValueError(
                        f"color_map value {dst!r} is not a valid color; valid colors are {COLORS}."
                    )

        if reflect not in ("none", "vertical", "horizontal"):
            raise ValueError(
                "reflect must be one of 'none', 'vertical', or 'horizontal', "
                f"got {reflect!r}."
            )

        rows = [r for r in src_rows if 1 <= r <= self.height]
        cols = [c for c in src_columns if 1 <= c <= self.width]
        if not rows or not cols:
            return []

        row_min, row_max = min(rows), max(rows)
        col_min, col_max = min(cols), max(cols)

        # Snapshot source colors so copying works even when regions overlap.
        src_colors: dict[tuple[int, int], str] = {}
        for r in rows:
            for c in cols:
                src_colors[(r, c)] = Tile(r, c, self).color

        dest_tiles: list[Tile] = []
        for r in rows:
            for c in cols:
                src_color = src_colors[(r, c)]

                if reflect == "vertical":
                    r2, c2 = r, col_min + col_max - c
                elif reflect == "horizontal":
                    r2, c2 = row_min + row_max - r, c
                else:
                    r2, c2 = r, c

                dest_r = r2 + drow
                dest_c = c2 + dcol
                if 1 <= dest_r <= self.height and 1 <= dest_c <= self.width:
                    dest_tile = Tile(dest_r, dest_c, self)
                    new_color = color_map.get(src_color, src_color) if color_map else src_color
                    dest_tile.draw(new_color)
                    dest_tiles.append(dest_tile)

        return dest_tiles


    def mirror_horizontal(
        self,
        axis_row: int,
        rows: range | None = None,
        color_map: dict[str, str] | None = None,
    ) -> "Game":
        """Mirror tiles across a horizontal axis passing through ``axis_row``.

        Colors in the source region are optionally remapped using ``color_map``
        as they are copied to their mirrored positions.

        This operation is a *copy*, not a swap: the specified rows act as the
        source, and their mirrored counterparts are overwritten.

        Args:
            axis_row: Row index (1-based) of the horizontal axis.
            rows: Optional range of source rows to mirror. If ``None``,
                the entire board height is used.
            color_map: Optional mapping ``{source_color: dest_color}`` applied
                during copying. Colors not in the map are copied unchanged.

        Returns:
            The mutated ``Game`` instance (for chaining).

        Raises:
            TypeError: If ``rows`` is not a ``range`` (when provided), or if
                ``color_map`` is not a dict.
            ValueError: If ``axis_row`` is outside the board.
            ValueError: If ``color_map`` keys or values are not valid color names.

        Examples:
            >>> g = Game(width=3, height=3)
            >>> Tile(1, 2, g).draw('blue')
            Tile(row=1, column=2, color=blue)
            >>> _ = g.mirror_horizontal(axis_row=2)
            >>> [Tile(r, 2, g).color for r in range(1, 4)]
            ['blue', 'white', 'blue']
        """
        if not isinstance(axis_row, int):
            raise TypeError(f"axis_row must be an int, got {type(axis_row).__name__}.")
        if not (1 <= axis_row <= self.height):
            raise ValueError(
                f"axis_row {axis_row} is outside the board; valid rows are 1..{self.height}."
            )

        if rows is None:
            rows = range(1, self.height + 1)
        elif not isinstance(rows, range):
            raise TypeError(f"rows must be a range or None, got {type(rows).__name__}.")

        if color_map is not None and not isinstance(color_map, dict):
            raise TypeError(f"color_map must be a dict or None, got {type(color_map).__name__}.")

        if color_map:
            for src, dst in color_map.items():
                if src not in COLORS:
                    raise ValueError(
                        f"color_map key {src!r} is not a valid color; valid colors are {COLORS}."
                    )
                if dst not in COLORS:
                    raise ValueError(
                        f"color_map value {dst!r} is not a valid color; valid colors are {COLORS}."
                    )

        for r in rows:
            if not (1 <= r <= self.height):
                continue
            for c in range(1, self.width + 1):
                src_tile = Tile(r, c, self)
                src_color = src_tile.color
                dest_r = 2 * axis_row - r
                if 1 <= dest_r <= self.height:
                    dest_tile = Tile(dest_r, c, self)
                    new_color = color_map.get(src_color, src_color) if color_map else src_color
                    dest_tile.draw(new_color)

        return self


    def mirror_vertical(
        self,
        axis_column: int,
        columns: range | None = None,
        color_map: dict[str, str] | None = None,
    ) -> "Game":
        """Mirror tiles across a vertical axis passing through ``axis_column``.

        Colors in the source region are optionally remapped using ``color_map``
        as they are copied to their mirrored positions.

        This operation is a *copy*, not a swap: the specified columns act as
        the source, and their mirrored counterparts are overwritten.

        Args:
            axis_column: Column index (1-based) of the vertical axis.
            columns: Optional range of source columns to mirror. If ``None``,
                the entire board width is used.
            color_map: Optional mapping ``{source_color: dest_color}`` applied
                during copying. Colors not in the map are copied unchanged.

        Returns:
            The mutated ``Game`` instance (for chaining).

        Raises:
            TypeError: If ``columns`` is not a ``range`` (when provided), or if
                ``color_map`` is not a dict.
            ValueError: If ``axis_column`` is outside the board.
            ValueError: If ``color_map`` keys or values are not valid color names.

        Examples:
            >>> g = Game(width=4, height=1)
            >>> Tile(1, 1, g).draw('red')
            Tile(row=1, column=1, color=red)
            >>> _ = g.mirror_vertical(axis_column=2)
            >>> [Tile(1, c, g).color for c in range(1, 5)]
            ['white', 'white', 'red', 'white']
        """
        if not isinstance(axis_column, int):
            raise TypeError(f"axis_column must be an int, got {type(axis_column).__name__}.")
        if not (1 <= axis_column <= self.width):
            raise ValueError(
                f"axis_column {axis_column} is outside the board; valid columns are 1..{self.width}."
            )

        if columns is None:
            columns = range(1, self.width + 1)
        elif not isinstance(columns, range):
            raise TypeError(f"columns must be a range or None, got {type(columns).__name__}.")

        if color_map is not None and not isinstance(color_map, dict):
            raise TypeError(f"color_map must be a dict or None, got {type(color_map).__name__}.")

        # Validate color_map entries early for clearer error messages
        if color_map:
            for src, dst in color_map.items():
                if src not in COLORS:
                    raise ValueError(
                        f"color_map key {src!r} is not a valid color; valid colors are {COLORS}."
                    )
                if dst not in COLORS:
                    raise ValueError(
                        f"color_map value {dst!r} is not a valid color; valid colors are {COLORS}."
                    )

        for r in range(1, self.height + 1):
            for c in columns:
                if not (1 <= c <= self.width):
                    continue
                src_tile = Tile(r, c, self)
                src_color = src_tile.color
                dest_c = 2 * axis_column - c
                if 1 <= dest_c <= self.width:
                    dest_tile = Tile(r, dest_c, self)
                    new_color = color_map.get(src_color, src_color) if color_map else src_color
                    dest_tile.draw(new_color)

        return self


    def triangle(
        self,
        apex: Tile | tuple[int, int],
        direction: str,
        side: int,
        filled: bool = True,
    ) -> list[Tile]:
        """Construct an equilateral triangle of hex tiles.

        The triangle has its apex at ``apex`` and is oriented in ``direction``.
        The orientation indicates the direction *from the apex toward the base*.
        For example, ``direction='down'`` gives a triangle whose apex is above
        its base, extending downward.

        Args:
            apex: Apex position as a ``Tile`` or ``(row, column)`` tuple.
            direction: Orientation of the triangle, one of ``DIRECTIONS``.
            side: Length of each side (number of tiles along an edge), must be
                at least 1.
            filled: If ``True``, return all tiles inside the triangle, otherwise
                only the border tiles.

        Returns:
            A list of ``Tile`` objects making up the triangle.

        Raises:
            TypeError: If ``apex`` is not a ``Tile`` or ``(row, column)`` tuple,
                or if ``side``/``filled`` have the wrong types.
            ValueError: If ``apex`` is outside the board.
            ValueError: If ``direction`` is invalid.
            ValueError: If ``side`` is less than 1.
            ValueError: If ``apex`` is a ``Tile`` from a different ``Game``.

        Examples:
            >>> g = Game(width=7, height=7)
            >>> tris = g.triangle((4, 4), direction='down', side=2, filled=True)
            >>> sorted((t.row, t.column) for t in tris)
            [(4, 4), (4, 5), (5, 3)]
        """
        def _coerce_to_row_col(pos, name: str) -> tuple[int, int]:
            if isinstance(pos, Tile):
                if pos.game is not self:
                    raise ValueError(
                        f"{name} Tile belongs to a different Game instance; "
                        "use a Tile from this Game or pass a (row, column) tuple."
                    )
                return pos.row, pos.column
            if not (isinstance(pos, tuple) and len(pos) == 2):
                raise TypeError(
                    f"{name} must be a Tile or a (row, column) tuple, got {type(pos).__name__}."
                )
            row, col = pos
            if not isinstance(row, int) or not isinstance(col, int):
                raise TypeError(
                    f"{name} row and column must be integers, got {type(row).__name__} and {type(col).__name__}."
                )
            return row, col

        if not isinstance(side, int):
            raise TypeError(f"side must be an int, got {type(side).__name__}.")
        if side < 1:
            raise ValueError("side must be at least 1.")

        if not isinstance(filled, bool):
            raise TypeError(f"filled must be a bool, got {type(filled).__name__}.")

        direction_steps: dict[str, tuple[int, int]] = {
            "up": (-1, 0),
            "up_right": (-1, 1),
            "down_right": (0, 1),
            "down": (1, 0),
            "down_left": (1, -1),
            "up_left": (0, -1),
        }
        order = ["up", "up_right", "down_right", "down", "down_left", "up_left"]

        if direction not in direction_steps:
            raise ValueError(
                f"direction must be one of {sorted(direction_steps)}, got {direction!r}."
            )

        row0, col0 = _coerce_to_row_col(apex, "apex")
        apex_tile = Tile(row0, col0, self)
        if not apex_tile.on_board():
            raise ValueError(
                f"apex {apex_tile} is outside the board; "
                "triangle() requires the apex to be on the board."
            )

        # Triangle sides extend from the apex in the two directions adjacent to
        # the orientation direction around the hex.
        idx = order.index(direction)
        dir1 = order[(idx - 1) % 6]
        dir2 = order[(idx + 1) % 6]
        dr1, dc1 = direction_steps[dir1]
        dr2, dc2 = direction_steps[dir2]

        tiles: list[Tile] = []

        # Barycentric-style fill: positions apex + i*dir1 + j*dir2 with i,j >= 0
        # and i + j < side. Border is where i == 0, j == 0, or i + j == side-1.
        for i in range(side):
            for j in range(side - i):
                r = row0 + i * dr1 + j * dr2
                c = col0 + i * dc1 + j * dc2
                t = Tile(r, c, self)
                if not t.on_board():
                    continue
                if filled or i == 0 or j == 0 or (i + j) == (side - 1):
                    tiles.append(t)

        return tiles


    def path(self, start: Tile | tuple[int, int], steps: list[str]) -> list[Tile]:
        """Follow a sequence of hex directions starting from ``start``.

        The path always includes the starting tile as the first element and then
        moves one step for each direction in ``steps``, stopping if it leaves
        the board.

        Args:
            start: Starting position, as a ``Tile`` or ``(row, column)`` tuple.
            steps: A list of direction names (each one of ``DIRECTIONS``).

        Returns:
            A list of visited ``Tile`` objects, including the starting tile.
            If a step would move off the board, the path stops before that move.

        Raises:
            TypeError: If ``start`` is not a ``Tile`` or ``(row, column)`` tuple,
                or if ``steps`` is not a list of strings.
            ValueError: If ``start`` is outside the board.
            ValueError: If any direction string is invalid.
            ValueError: If ``start`` is a ``Tile`` from a different ``Game``.

        Examples:
            >>> g = Game(width=5, height=5)
            >>> p = g.path((3, 3), ['up', 'up_right', 'down_right'])
            >>> [(t.row, t.column) for t in p]
            [(3, 3), (2, 3), (1, 4), (1, 5)]
        """
        def _coerce_to_row_col(pos, name: str) -> tuple[int, int]:
            if isinstance(pos, Tile):
                if pos.game is not self:
                    raise ValueError(
                        f"{name} Tile belongs to a different Game instance; "
                        "use a Tile from this Game or pass a (row, column) tuple."
                    )
                return pos.row, pos.column
            if not (isinstance(pos, tuple) and len(pos) == 2):
                raise TypeError(
                    f"{name} must be a Tile or a (row, column) tuple, got {type(pos).__name__}."
                )
            row, col = pos
            if not isinstance(row, int) or not isinstance(col, int):
                raise TypeError(
                    f"{name} row and column must be integers, got {type(row).__name__} and {type(col).__name__}."
                )
            return row, col

        if not isinstance(steps, list):
            raise TypeError(f"steps must be a list of direction strings, got {type(steps).__name__}.")

        direction_steps: dict[str, tuple[int, int]] = {
            "up": (-1, 0),
            "down": (1, 0),
            "up_right": (-1, 1),
            "down_left": (1, -1),
            "up_left": (0, -1),
            "down_right": (0, 1),
        }

        for d in steps:
            if not isinstance(d, str):
                raise TypeError(
                    f"Each step must be a direction string, got {type(d).__name__}."
                )
            if d not in direction_steps:
                raise ValueError(
                    f"Invalid direction {d!r} in steps; valid directions are "
                    f"{sorted(direction_steps)}."
                )

        row, col = _coerce_to_row_col(start, "start")
        start_tile = Tile(row, col, self)
        if not start_tile.on_board():
            raise ValueError(
                f"start {start_tile} is outside the board; "
                "path() requires a starting position on the board."
            )

        tiles: list[Tile] = [start_tile]
        for d in steps:
            dr, dc = direction_steps[d]
            row += dr
            col += dc
            t = Tile(row, col, self)
            if not t.on_board():
                break
            tiles.append(t)
        return tiles


    def line_between(
        self,
        a: Tile | tuple[int, int],
        b: Tile | tuple[int, int],
    ) -> list[Tile]:
        """Return the straight hex line of tiles connecting ``a`` and ``b``.

        The two endpoints must lie on one of the three hex axes; that is, they
        must be collinear on the hex grid. If they are not, a ``ValueError`` is
        raised.

        Args:
            a: First endpoint, as a ``Tile`` or ``(row, column)`` tuple.
            b: Second endpoint, as a ``Tile`` or ``(row, column)`` tuple.

        Returns:
            A list of ``Tile`` objects from ``a`` to ``b`` (inclusive), ordered
            from ``a`` to ``b``.

        Raises:
            TypeError: If either endpoint is not a ``Tile`` or ``(row, column)`` tuple.
            ValueError: If either endpoint is outside the board.
            ValueError: If the endpoints are not collinear on a hex axis.
            ValueError: If an endpoint is a ``Tile`` from a different ``Game``.

        Examples:
            >>> g = Game(width=5, height=5)
            >>> [(t.row, t.column) for t in g.line_between((2, 2), (4, 2))]
            [(2, 2), (3, 2), (4, 2)]
            >>> g.line_between((2, 2), (4, 4))
            Traceback (most recent call last):
            ...
            ValueError: Tiles (2, 2) and (4, 4) are not on a straight hex axis; \
    line_between() can only connect collinear hexes.
        """
        def _coerce_to_row_col(pos, name: str) -> tuple[int, int]:
            if isinstance(pos, Tile):
                if pos.game is not self:
                    raise ValueError(
                        f"{name} Tile belongs to a different Game instance; "
                        "use a Tile from this Game or pass a (row, column) tuple."
                    )
                return pos.row, pos.column
            if not (isinstance(pos, tuple) and len(pos) == 2):
                raise TypeError(
                    f"{name} must be a Tile or a (row, column) tuple, got {type(pos).__name__}."
                )
            row, col = pos
            if not isinstance(row, int) or not isinstance(col, int):
                raise TypeError(
                    f"{name} row and column must be integers, got {type(row).__name__} and {type(col).__name__}."
                )
            return row, col

        r1, c1 = _coerce_to_row_col(a, "a")
        r2, c2 = _coerce_to_row_col(b, "b")

        t1 = Tile(r1, c1, self)
        t2 = Tile(r2, c2, self)
        if not t1.on_board():
            raise ValueError(
                f"Endpoint a {t1} is outside the board; line_between() requires both "
                "endpoints to be on the board."
            )
        if not t2.on_board():
            raise ValueError(
                f"Endpoint b {t2} is outside the board; line_between() requires both "
                "endpoints to be on the board."
            )

        # Same tile: degenerate line
        if r1 == r2 and c1 == c2:
            return [t1]

        # Axial coordinates (q, r) with 0-based indices
        q1, a1 = c1 - 1, r1 - 1
        q2, a2 = c2 - 1, r2 - 1

        # Collinearity on hex grid: same q, same r, or same (q + r)
        if not (q1 == q2 or a1 == a2 or (q1 + a1) == (q2 + a2)):
            raise ValueError(
                f"Tiles ({r1}, {c1}) and ({r2}, {c2}) are not on a straight hex axis; "
                "line_between() can only connect collinear hexes."
            )

        # Hex distance
        dist = (
            abs(q1 - q2)
            + abs(a1 - a2)
            + abs((q1 + a1) - (q2 + a2))
        ) // 2

        def _sign(x: int) -> int:
            return (x > 0) - (x < 0)

        dq = _sign(q2 - q1)
        da = _sign(a2 - a1)

        # Convert axial step (da, dq) back to (dr, dc) in 1-based board coordinates
        dr, dc = da, dq

        row, col = r1, c1
        tiles: list[Tile] = []
        for _ in range(dist + 1):
            tiles.append(Tile(row, col, self))
            row += dr
            col += dc

        return tiles


    def ray(
        self,
        start: Tile | tuple[int, int],
        direction: str,
        length: int | None = None,
    ) -> list[Tile]:
        """Return a straight ray of tiles from ``start`` in ``direction``.

        The ray always includes the starting tile and then walks one hex at a
        time in the given direction until either:

        * The board edge is reached, or
        * ``length`` steps have been taken (if ``length`` is not ``None``).

        Args:
            start: Starting position, as a ``Tile`` or ``(row, column)`` tuple.
            direction: One of ``DIRECTIONS``.
            length: Maximum number of steps after the start (``None`` for
                “until the board edge”). A length of 0 returns only the start.

        Returns:
            A list of ``Tile`` objects on the ray, including ``start``.

        Raises:
            TypeError: If ``start`` is not a ``Tile`` or ``(row, column)`` tuple,
                or if ``length`` is not an integer or ``None``.
            ValueError: If ``start`` is outside the board.
            ValueError: If ``direction`` is not one of the allowed values.
            ValueError: If ``length`` is negative.
            ValueError: If ``start`` is a ``Tile`` from a different ``Game``.

        Examples:
            >>> g = Game(width=5, height=5)
            >>> [ (t.row, t.column) for t in g.ray((3, 3), 'up') ]
            [(3, 3), (2, 3), (1, 3)]
            >>> [ (t.row, t.column) for t in g.ray((3, 3), 'down', length=1) ]
            [(3, 3), (4, 3)]
        """
        def _coerce_to_row_col(pos, name: str) -> tuple[int, int]:
            if isinstance(pos, Tile):
                if pos.game is not self:
                    raise ValueError(
                        f"{name} Tile belongs to a different Game instance; "
                        "use a Tile from this Game or pass a (row, column) tuple."
                    )
                return pos.row, pos.column
            if not (isinstance(pos, tuple) and len(pos) == 2):
                raise TypeError(
                    f"{name} must be a Tile or a (row, column) tuple, got {type(pos).__name__}."
                )
            row, col = pos
            if not isinstance(row, int) or not isinstance(col, int):
                raise TypeError(
                    f"{name} row and column must be integers, got {type(row).__name__} and {type(col).__name__}."
                )
            return row, col

        direction_steps: dict[str, tuple[int, int]] = {
            "up": (-1, 0),
            "down": (1, 0),
            "up_right": (-1, 1),
            "down_left": (1, -1),
            "up_left": (0, -1),
            "down_right": (0, 1),
        }

        if direction not in direction_steps:
            raise ValueError(
                f"direction must be one of {sorted(direction_steps)}, got {direction!r}."
            )

        if length is not None and not isinstance(length, int):
            raise TypeError(
                f"length must be an int or None, got {type(length).__name__}."
            )
        if isinstance(length, int) and length < 0:
            raise ValueError("length must be non-negative.")

        row, col = _coerce_to_row_col(start, "start")
        start_tile = Tile(row, col, self)
        if not start_tile.on_board():
            raise ValueError(
                f"start {start_tile} is outside the board; "
                "ray() requires a starting position on the board."
            )

        tiles: list[Tile] = [start_tile]
        dr, dc = direction_steps[direction]

        if length is None:
            # Walk until board edge
            while True:
                row += dr
                col += dc
                t = Tile(row, col, self)
                if not t.on_board():
                    break
                tiles.append(t)
        else:
            for _ in range(length):
                row += dr
                col += dc
                t = Tile(row, col, self)
                if not t.on_board():
                    break
                tiles.append(t)
        return tiles


    def ring(self, center: Tile | tuple[int, int], radius: int) -> list[Tile]:
        """Return all tiles at exactly the given hex-distance from ``center``.

        The distance is computed on a hex grid using axial coordinates derived
        from (row, column). The returned tiles are always clipped to the board.

        Args:
            center: The center position, either a ``Tile`` or a ``(row, column)`` tuple.
            radius: Non-negative hex distance from ``center``.

        Returns:
            A list of ``Tile`` objects whose hex-distance from ``center`` is
            exactly ``radius``. The list is empty if no tiles on the board are
            at that distance.

        Raises:
            TypeError: If ``center`` is not a ``Tile`` or ``(row, column)`` tuple,
                or if ``radius`` is not an integer.
            ValueError: If ``radius`` is negative.
            ValueError: If ``center`` is a ``Tile`` from a different ``Game``.

        Examples:
            >>> g = Game(width=5, height=5)
            >>> center = Tile(3, 3, g)
            >>> sorted((t.row, t.column) for t in g.ring(center, 1))
            [(2, 3), (2, 4), (3, 2), (3, 4), (4, 2), (4, 3)]
            >>> # Radius 0 only returns the center tile (if it is on the board)
            >>> sorted((t.row, t.column) for t in g.ring((3, 3), 0))
            [(3, 3)]
        """
        def _coerce_to_row_col(pos, name: str) -> tuple[int, int]:
            if isinstance(pos, Tile):
                if pos.game is not self:
                    raise ValueError(
                        f"{name} Tile belongs to a different Game instance; "
                        "use a Tile from this Game or pass a (row, column) tuple."
                    )
                return pos.row, pos.column
            if not (isinstance(pos, tuple) and len(pos) == 2):
                raise TypeError(
                    f"{name} must be a Tile or a (row, column) tuple, got {type(pos).__name__}."
                )
            row, col = pos
            if not isinstance(row, int) or not isinstance(col, int):
                raise TypeError(
                    f"{name} row and column must be integers, got {type(row).__name__} and {type(col).__name__}."
                )
            return row, col

        if not isinstance(radius, int):
            raise TypeError(f"radius must be an int, got {type(radius).__name__}.")
        if radius < 0:
            raise ValueError("radius must be non-negative.")

        center_row, center_col = _coerce_to_row_col(center, "center")

        def _hex_distance(r1: int, c1: int, r2: int, c2: int) -> int:
            # Treat (row, column) as axial (r, q) with 0-based indices
            q1, a1 = c1 - 1, r1 - 1
            q2, a2 = c2 - 1, r2 - 1
            return (
                abs(q1 - q2)
                + abs(a1 - a2)
                + abs((q1 + a1) - (q2 + a2))
            ) // 2

        tiles: list[Tile] = []
        for r in range(1, self.height + 1):
            for c in range(1, self.width + 1):
                if _hex_distance(center_row, center_col, r, c) == radius:
                    tiles.append(Tile(r, c, self))
        return tiles


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


    def neighbors(self) -> list["Tile"]:
        """Return the list of hex-adjacent tiles (distance 1).

        A tile can have between 0 and 6 neighbors depending on its position on
        the board. Tiles that would fall outside the board are omitted.

        Args:
            None

        Returns:
            A list of Tile instances that are at hex distance 1 from this tile.
            If this tile is off the board (``on_board()`` is False), an empty list
            is returned.

        Examples:
            Get the neighbors of a center tile on a small board:

            >>> from hexagen import Game, Tile
            >>> with Game(width=4, height=3) as g:
            ...     center = Tile(2, 2)
            ...     sorted((t.row, t.column) for t in center.neighbors())
            [(1, 1), (1, 2), (1, 3), (2, 1), (2, 3), (3, 2)]

            Corner tiles naturally have fewer neighbors:

            >>> with Game(width=4, height=3) as g:
            ...     corner = Tile(1, 1)
            ...     sorted((t.row, t.column) for t in corner.neighbors())
            [(1, 2), (2, 1), (2, 2)]

            Off-board tiles have no on-board neighbors:

            >>> with Game(width=4, height=3) as g:
            ...     off = Tile(0, 0)
            ...     off.neighbors()
            []
        """
        if self.game is None:
            raise RuntimeError(
                "Tile has no associated Game instance. "
                "Ensure tiles are created with a Game, e.g. "
                "'with Game() as g: Tile(1, 1, game=g)'."
            )

        # If this tile is not on the board, there are no valid neighbors
        if not self.on_board():
            return []

        row = self.row
        col = self.column
        height = self.game.height
        width = self.game.width

        # Vertical neighbors (same column)
        candidates = [
            (row - 1, col),  # up
            (row + 1, col),  # down
        ]

        # Diagonal neighbors depend on column parity (vertical offset hex layout)
        if col % 2 == 1:
            # Odd columns are shifted down relative to even columns
            candidates.extend(
                [
                    (row, col - 1),      # up_left
                    (row, col + 1),      # up_right
                    (row + 1, col - 1),  # down_left
                    (row + 1, col + 1),  # down_right
                ]
            )
        else:
            # Even columns are shifted up relative to odd columns
            candidates.extend(
                [
                    (row - 1, col - 1),  # up_left
                    (row - 1, col + 1),  # up_right
                    (row, col - 1),      # down_left
                    (row, col + 1),      # down_right
                ]
            )

        neighbors = []
        for r, c in candidates:
            if 1 <= r <= height and 1 <= c <= width:
                neighbors.append(Tile(row=r, column=c, game=self.game))

        return neighbors
