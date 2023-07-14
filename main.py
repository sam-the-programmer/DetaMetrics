import os
import typing as t

import deta
import fastapi
import jinja2 as j2
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

app = fastapi.FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")

backend = deta.Deta()
is_dev = os.getenv("DETA_RUNTIME") is None
db_prefix = "dev-" if is_dev else ""

base = backend.Base(f"{db_prefix}metrics")
meta = backend.Base(f"{db_prefix}meta")

palette = [
    "rgb(255, 99, 132)",  # different order to ensure contrast if only two or three lines plotted
    "rgb(54, 162, 235)",
    "rgb(255, 205, 86)",
    "rgb(75, 192, 192)",
    "rgb(255, 159, 64)",
    "rgb(100, 39, 235)",
]

transparent_palette = [i.replace("rgb", "rgba").replace(")", ", 0.2)") for i in palette]


with open("static/templates/base.html") as file:
    BASE_TEMPLATE = j2.Template(file.read())

with open("static/templates/chart.html") as file:
    CHART_TEMPLATE = j2.Template(file.read())

with open("static/templates/chartmarkup.html") as file:
    CMK_TEMPLATE = j2.Template(file.read())

with open("static/templates/chartscript.js") as file:
    SCRIPT_TEMPLATE = j2.Template(file.read())


class Templater:
    @staticmethod
    def dataset(
        name: str,
        data: t.List[float],
        ind: int = 0,
    ) -> str:
        ind += 1
        return f"""{{label: '{name.title()}', data: {data}, backgroundColor: '{transparent_palette[ind % len(transparent_palette)]}', borderColor: '{palette[ind % len(palette)]}'}}"""

    @staticmethod
    def list_to_string(data: t.List[str]) -> str:
        return f"[{', '.join(data)}]"

    @staticmethod
    def chart(
        name: str,
        labels: t.List[str],
        datasets: t.List[str],
        x_axis: str = "Timestep",
        y_axis: str = "Value",
        i: int = 0,
    ) -> str:
        return CHART_TEMPLATE.render(
            i=i,
            name=name[0].upper() + name[1:],
            labels=Templater.list_to_string([f'"{j}"' for j in labels]),
            datasets=Templater.list_to_string(datasets),
            x_axis=x_axis,
            y_axis=y_axis,
        )

    @staticmethod
    def dashboard(
        charts: t.List[str],
        title: str = "Dashboard",
        dark: bool = False,
    ) -> str:
        charts = charts if len(charts) > 0 else ["<h1>No data to display.</h1>"]

        return BASE_TEMPLATE.render(
            title=title,
            charts="\n".join(charts),
            bodyClasses=f"class=\"{'dark' if dark else ''}\"",
        )


def get_charts():
    db = base.fetch().items

    charts = []
    for i in db:
        datasets = []
        datasets.extend(
            Templater.dataset(k, v, len(datasets) - 1)
            for k, v in i["metrics"].items()
        )
        max_len = max(len(i["metrics"][k]) for i in db for k in i["metrics"])
        labels = [str(i) for i in range(max_len)]

        charts.append(
            Templater.chart(
                name=i["key"],
                labels=labels,
                datasets=datasets,
                x_axis="Timestep",
                y_axis="Value",
                i=len(charts),
            )
        )

    return charts


@app.get("/", response_class=HTMLResponse)
async def index(dark: bool = False) -> str:
    charts = get_charts()

    return Templater.dashboard(title="DetaMetrics | Dashboard", charts=charts, dark=dark)


@app.get("/charts")
async def charts() -> t.Tuple[str, str]:
    db = base.fetch().items

    charts = []
    codes = []
    for i in db:
        datasets = []
        datasets.extend(
            Templater.dataset(k, v, len(datasets) - 1)
            for k, v in i["metrics"].items()
        )
        max_len = max(len(i["metrics"][k]) for i in db for k in i["metrics"])
        labels = [str(i) for i in range(max_len)]

        codes.append(
            SCRIPT_TEMPLATE.render(
                i=len(codes),
                datasets=Templater.list_to_string(datasets),
                labels=Templater.list_to_string([f'"{j}"' for j in labels]),
            )
        )

        name = i["key"][0].upper() + i["key"][1:]
        charts.append(
            CMK_TEMPLATE.render(
                i=len(charts),
                name=name,
            )
        )

    oHtml, oScript = "\n".join(charts), "\n".join(codes)
    return ("<h1>No data to display.</h1>", "") if not oHtml else (oHtml, oScript)


@app.get("/set/{graph}/{name}/{value}")
async def set(graph: str, name: str, value: float) -> dict[str, str]:
    if base.get(graph) is None:
        base.put({"key": graph, "metrics": {name: [value]}})
    else:
        data = base.get(graph)
        if name in data["metrics"]:
            data["metrics"][name].append(value)
        else:
            data["metrics"][name] = [value]

        base.put(data)

    return {"status": "ok"}


@app.get("/clear/{graph}")
async def clear(graph: str) -> dict[str, str]:
    base.delete(graph)
    return {"status": "ok"}


@app.get("/clear/{graph}/{name}")
async def delete(graph: str, name: str) -> dict[str, str]:
    data = base.get(graph)
    del data["metrics"][name]
    base.put(data)
    return {"status": "ok"}


@app.get("/clear")
async def clear_all() -> dict[str, str]:
    for i in [i["key"] for i in base.fetch().items]:
        base.delete(i)

    return {"status": "ok"}
