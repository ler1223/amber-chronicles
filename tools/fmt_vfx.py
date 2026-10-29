"""Компактная запись data/vfx.json: заготовка — строка, слой таймлайна — строка, навык — строка.

python tools/fmt_vfx.py          переписать файл в этом виде (после правок скриптом)
"""
import json
import os

PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "vfx.json")


def dump(d):
    j = lambda v: json.dumps(v, ensure_ascii=False)  # noqa: E731
    parts = []
    for section, body in d.items():
        if section == "effects":
            rows = []
            for name, layers in body.items():
                inner = ",\n".join(f"      {j(layer)}" for layer in layers)
                rows.append(f'    {j(name)}: [\n{inner}\n    ]')
            parts.append(f'  {j(section)}: {{\n' + ",\n".join(rows) + "\n  }")
        elif isinstance(body, dict) and body and all(isinstance(v, dict) for v in body.values()):
            rows = [f"    {j(k)}: {j(v)}" for k, v in body.items()]
            parts.append(f'  {j(section)}: {{\n' + ",\n".join(rows) + "\n  }")
        else:
            parts.append(f"  {j(section)}: {j(body)}")
    return "{\n" + ",\n\n".join(parts) + "\n}\n"


if __name__ == "__main__":
    with open(PATH, encoding="utf-8") as f:
        data = json.load(f)
    with open(PATH, "w", encoding="utf-8", newline="\n") as f:
        f.write(dump(data))
