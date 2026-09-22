# Kapsel Aria2 Plugin (`kps aria2` / `kps down`)

High-speed concurrent download accelerator powered by `aria2c`.

## Default Concurrency Parameters
- **`-s 16`**: 16 connection splits per file download.
- **`-x 16`**: 16 max connections to the same server.
- **`-j 4`**: Maximum 4 parallel files downloaded simultaneously.
- **`-k 1M`**: Minimum 1MB chunk size so multi-threaded splitting activates even for small-medium files.
- **`-c`**: Automatically continue/resume incomplete downloads.

## Usage

```bash
# Basic download (using default -s 16, -x 16, -j 4)
kps aria2 https://example.com/file.zip

# Quick alias
kps down https://example.com/file.zip

# Multiple parallel downloads (up to 4 concurrently, rest queued)
kps aria2 https://example.com/file1.zip https://example.com/file2.zip https://example.com/file3.zip

# Batch download from text file
kps aria2 -i urls.txt

# Specify output name or destination directory
kps aria2 -o archive.zip https://example.com/file.zip
kps aria2 -d ~/Downloads https://example.com/file.zip

# Inspect current configuration
kps aria2 config

# Customizing default parameters
kps aria2 config split 32       # Set default -s to 32
kps aria2 config conn 32        # Set default -x to 32
kps aria2 config jobs 8         # Set default -j to 8
kps aria2 config reset          # Restore factory defaults (-s 16, -x 16, -j 4)
```
