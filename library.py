"""Lazy folder tree for the library pane.

Nothing is walked recursively: a node's children are listed the first time it is
expanded, so pointing at a root with hundreds of shows costs one scandir.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import scanner


@dataclass
class Node:
    path: Path
    kind: str                      # root | folder | show | season | movie | episode
    video: Path | None = None
    season: int | None = None
    episode: int | None = None
    parent: "Node | None" = None
    children: list["Node"] = field(default_factory=list)
    loaded: bool = False

    @property
    def is_dir(self) -> bool:
        return self.kind != "movie" or self.video is None

    @property
    def label(self) -> str:
        if self.kind == "episode":
            title = scanner.episode_title(self.path.name)
            tag = f"S{self.season or 0:02d}E{self.episode or 0:02d}"
            return f"{tag} · {title}" if title else tag
        return self.path.name

    def walk(self):
        yield self
        for child in self.children:
            yield from child.walk()


def detect_dir(path: Path) -> str:
    if scanner._looks_like_show(path):
        return "show"
    videos = scanner._videos(path)
    if videos:
        return "movie"
    return "folder"


def _primary_video(folder: Path) -> Path | None:
    """Pick the largest video in a movie folder as the primary file."""
    videos = scanner._videos(folder)
    if not videos:
        return None
    return max(videos, key=lambda p: p.stat().st_size, default=videos[0])


def _episode_nodes(parent: Node, folder: Path) -> list[Node]:
    nodes: list[Node] = []
    for video in scanner._videos(folder):
        match = scanner.SXXEXX.search(video.name)
        if not match:
            continue
        nodes.append(
            Node(
                path=video,
                kind="episode",
                video=video,
                season=int(match.group(1)),
                episode=int(match.group(2)),
                parent=parent,
            )
        )
    nodes.sort(key=lambda n: (n.season or 0, n.episode or 0))
    return nodes


def _season_dirs(folder: Path) -> list[Path]:
    return [
        d for d in scanner._subdirs(folder)
        if scanner.SEASON_DIR.match(d.name) or scanner.SPECIALS_DIR.match(d.name)
    ]


def children_of(node: Node) -> list[Node]:
    if node.loaded:
        return node.children

    kids: list[Node] = []
    if node.kind in ("root", "folder"):
        for sub in scanner._subdirs(node.path):
            kind = detect_dir(sub)
            video = None
            if kind == "movie":
                video = _primary_video(sub)
            kids.append(Node(path=sub, kind=kind, video=video, parent=node))
        for video in scanner._videos(node.path):
            kids.append(Node(path=video, kind="movie", video=video, parent=node))

    elif node.kind == "show":
        seasons = _season_dirs(node.path)
        if seasons:
            for sub in seasons:
                kids.append(
                    Node(
                        path=sub,
                        kind="season",
                        season=scanner._season_number(sub),
                        parent=node,
                    )
                )
        else:
            kids = _episode_nodes(node, node.path)

    elif node.kind == "season":
        kids = _episode_nodes(node, node.path)

    node.children = kids
    node.loaded = True
    return kids


def build_roots(paths: list[str]) -> list[Node]:
    roots: list[Node] = []
    for raw in paths:
        path = Path(raw)
        if path.exists() and path.is_dir():
            roots.append(Node(path=path, kind="root"))
    return roots


def node_for_path(root: Node, target: Path) -> Node | None:
    """Expand down to `target` if it lives under `root`."""
    target = target.resolve()
    node = root
    while True:
        if node.path.resolve() == target:
            return node
        children_of(node)
        match = None
        for child in node.children:
            if child.path.resolve() == target or target.is_relative_to(child.path.resolve()):
                match = child
                break
        if match is None:
            return None
        node = match
