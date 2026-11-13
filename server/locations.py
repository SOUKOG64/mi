"""Справочник локаций: кампус -> дом -> подъезд -> этаж (Vision, п. 5: «Выбор уровня локации»)."""

SEP = "/"
LEVEL_NAMES = {1: "Кампус", 2: "Дом", 3: "Подъезд", 4: "Этаж"}

_CAMPUSES = {"Кампус Север": 3, "Кампус Юг": 2}  # название -> число домов
_ENTRANCES = 3
_FLOORS = 5


def build_tree():
    tree = []
    for campus, houses in _CAMPUSES.items():
        house_nodes = []
        for h in range(1, houses + 1):
            entrances = []
            for e in range(1, _ENTRANCES + 1):
                floors = [{"name": f"Этаж {f}", "children": []} for f in range(1, _FLOORS + 1)]
                entrances.append({"name": f"Подъезд {e}", "children": floors})
            house_nodes.append({"name": f"Дом {h}", "children": entrances})
        tree.append({"name": campus, "children": house_nodes})
    return tree


TREE = build_tree()


def is_valid_path(path, min_depth=2):
    """Путь существует в справочнике и доходит минимум до дома."""
    if not isinstance(path, str) or not path:
        return False
    parts = path.split(SEP)
    if len(parts) < min_depth:
        return False
    nodes = TREE
    for name in parts:
        node = next((n for n in nodes if n["name"] == name), None)
        if node is None:
            return False
        nodes = node["children"]
    return True


def in_scope(location, prefix):
    """location лежит внутри prefix (или совпадает с ним)."""
    return location == prefix or location.startswith(prefix + SEP)


def prefix_for_level(location, level):
    parts = location.split(SEP)
    level = max(1, min(int(level), len(parts)))
    return SEP.join(parts[:level])
