from main import app
import json

app.openapi_schema = None

with open("docs/openapi.json", "w") as f:
    json.dump(app.openapi(), f, indent=2)