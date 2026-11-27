"""Erlaubt den Start mit ``python -m rootping`` (gleich wie der Befehl ``rootping``)."""

from rootping.cli import app

app(prog_name="rootping")
