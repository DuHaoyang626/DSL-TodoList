# JSON Fixture Runner

The JSON API tests are now executed manually through the interactive runner at `tests/test_json_api.py`. The script uses the real MySQL database and intentionally does **not** reset data between steps.

## Usage

1. Ensure MySQL is running and `db_utils.DB_CONFIG` points to the desired database.
2. Run the runner and provide the first JSON file (or press Enter to type it later):
   ```powershell
   python tests/test_json_api.py tests/fixtures/create_todo.json
   ```
3. After each step the script prints the request/response pair and asks for the next JSON file path. Press Enter with an empty value to stop the session.

## Context references

Fixtures may reference values from the previous response using the `$ref` helper. Example:

```json
{
  "id": {"$ref": "data.id"}
}
```

The example above injects the `id` value returned by the previous step into the next request. Expectations can also use `$ref` to compare against state from the earlier step.

## Provided fixtures

| File | Purpose |
| --- | --- |
| `tests/fixtures/create_todo.json` | Create a todo item for the flow |
| `tests/fixtures/read_created_todo.json` | Read the todo created in the previous step |
| `tests/fixtures/update_created_todo.json` | Update the todo retrieved by the read step |
| `tests/fixtures/delete_created_todo.json` | Delete the todo updated in the prior step |

Run them sequentially to cover create, read, update, and delete. Additional fixtures can be added following the same structure.
