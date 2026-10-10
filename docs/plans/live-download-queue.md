# Live download queue

Restore `dl-vid` as a standalone Python 3 command using the installed `yt-dlp`.
Installed commands are tracked using the `git-scripts` bare repository.
Development and verification happen in a writable checkout before installation
in `/usr/local/bin`.

- [x] Implement `dl-vid --tail FILE`, rereading the path after downloads and while idle so appended links and editor file replacements are recognized.
- [x] Support ordinary batch mode, comments, duplicate links, paths with spaces, and passing downloader options after `--`.
- [x] Persist completed URL entries separately from yt-dlp's download archive, bound retries, prevent simultaneous workers for the same state, and propagate Ctrl-C to the active downloader.
- [x] Verify changes during an active download, waiting at EOF, atomic editor saves, restart deduplication, controlled failures, and interruption using a fake downloader.
- [x] Format and review the script, tests, and plan, without tracking the launcher or other personal scripts.

Commit the implementation and this completed plan to the bare repository after
verification. Keep the installed script unchanged until the user installs the
tested version with sudo.

Intended defaults: poll every 2 seconds; retry failed URLs after 30 seconds, up to
3 attempts per invocation. Sidecar files beside the URL list retain completed
URLs and yt-dlp's completed video IDs. Removing a link stops future attempts;
it does not cancel an active download. Ctrl-C exits without marking an unfinished
download complete. Installation may require the user's sudo access.

## Usage

```bash
# Keep downloading as new links are saved to the file.
dl-vid --tail links.txt

# Process the file and exit when the queue and bounded retries are finished.
dl-vid links.txt

# Pass ordinary yt-dlp options after the separator.
dl-vid --tail links.txt -- -P ~/Videos --no-playlist
```

The default sidecars are `links.txt.dl-vid.json` (successful URL entries),
`links.txt.dl-vid.archive` (yt-dlp's completed video IDs), and
`links.txt.dl-vid.json.lock` (a worker lock; the empty file can remain after exit).
Use `--state-file` and `--archive` to choose other locations. This command runs
downloads; simulation, listing, and separate batch/archive options cannot be
forwarded because they conflict with completion tracking.
yt-dlp configuration files are not loaded, so settings such as format selection
and cookies must be supplied after `--`. This prevents metadata-only settings or
error-suppressing settings from marking an unfinished download complete.
Short downloader flags and their values must be separate arguments, for example
`-f bestaudio`, rather than combined flags or attached values.

Run the network-free integration tests with:

```bash
python3 -m unittest discover -s tests -p test_dl_vid.py -v
```
