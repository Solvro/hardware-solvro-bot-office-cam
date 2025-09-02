# hardware-solvro-bot-office-cam

#### Usage

To run locally with a file input:

```bash
uv run solvrocam file <path/to/file>
```

To stop seeing ultralytics logs in terminal output:

```bash
To disable Ultralytics logs:
uv run solvrocam file <path/to/file> 1>/dev/null
```

To stop seeing solvrocam logs in terminal output:

```bash
uv run solvrocam file <path/to/file> 2>/dev/null
```

To narrow the scope of solvrocam logs to a higher log level (DEBUG, INFO, WARNING, ERROR, CRITICAL):

```bash
LOG_LEVEL=WARNING uv run solvrocam file <path/to/file> 2>/dev/null
```

To stop seeing all terminal output:

```bash
uv run solvrocam file <path/to/file> &>/dev/null
```

To specify the processing stage output you want to see in the preview:

```bash
uv run solvrocam file -o captured <path/to/file>
```

see `uv run solvrocam file --help` for available stages
