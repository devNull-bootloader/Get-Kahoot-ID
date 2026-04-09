# Get-Kahoot-ID

A command-line tool that accepts a **Kahoot Game PIN** and returns the **Quiz ID**.

## Requirements

- Python 3.6+
- No external dependencies (uses only the Python standard library)

## Usage

### Pass the PIN as a command-line argument

```bash
python get_kahoot_id.py <game_pin>
```

Example:

```bash
python get_kahoot_id.py 1234567
```

### Interactive (prompted) mode

```bash
python get_kahoot_id.py
```

The script will prompt you to enter the PIN.

## Output

The script prints all HTTP response details (status code, headers, JSON body) as
well as any errors encountered during the request.  When the Quiz ID is found it
is printed as:

```
[✓] Quiz ID: <uuid>
```

The script exits with code **0** on success and **1** on failure.

## How It Works

1. Sends a `GET` request to `https://kahoot.it/reserve/session/<pin>/?<timestamp>`.
2. Prints the full HTTP response (status, headers, and JSON body).
3. Attempts to extract the Quiz UUID directly from the JSON response body.
4. If the UUID is not found directly, decodes the Kahoot session challenge using
   the `X-Kahoot-Session-Token` response header and checks the decoded payload.
5. Reports all errors (HTTP errors, network errors, JSON parse errors) with
   descriptive messages.