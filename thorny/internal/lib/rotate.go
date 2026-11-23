package lib

import (
	"fmt"
	"os"
	"path/filepath"
	"sync"
	"time"
)

// RotatingWriter writes into <dir>/<prefix><unix>.jsonl, where <unix> is the
// start of the current interval (aligned to full intervals in UTC, e.g.
// :00, :10, :20 for 10 minutes). A new file is opened on the first write in a
// new interval, so a file is never written to after its interval has ended.
// That is what upload.sh relies on: a file whose interval is over is complete.
type RotatingWriter struct {
	mu       sync.Mutex
	dir      string
	prefix   string
	interval int64 // seconds
	now      func() time.Time

	file        *os.File
	windowStart int64
}

func NewRotatingWriter(dir, prefix string, interval time.Duration) (*RotatingWriter, error) {
	if interval < time.Second {
		return nil, fmt.Errorf("rotation interval must be at least 1s, got %s", interval)
	}
	if err := os.MkdirAll(dir, 0o755); err != nil {
		return nil, err
	}
	return &RotatingWriter{
		dir:      dir,
		prefix:   prefix,
		interval: int64(interval / time.Second),
		now:      time.Now,
	}, nil
}

// Write writes p into the file of the current interval. slog handlers call
// Write once per record, so records are never split across files.
func (w *RotatingWriter) Write(p []byte) (int, error) {
	w.mu.Lock()
	defer w.mu.Unlock()

	start := w.now().Unix() / w.interval * w.interval
	if w.file == nil || start != w.windowStart {
		if err := w.open(start); err != nil {
			return 0, err
		}
	}
	return w.file.Write(p)
}

// open closes the current file and opens (or appends to) the file of the
// interval starting at start. Caller must hold w.mu.
func (w *RotatingWriter) open(start int64) error {
	if w.file != nil {
		_ = w.file.Close()
		w.file = nil
	}
	f, err := os.OpenFile(w.pathFor(start), os.O_APPEND|os.O_CREATE|os.O_WRONLY, 0o644)
	if err != nil {
		return err
	}
	w.file = f
	w.windowStart = start
	return nil
}

func (w *RotatingWriter) pathFor(start int64) string {
	return filepath.Join(w.dir, fmt.Sprintf("%s%d.jsonl", w.prefix, start))
}

// Close closes the current file. A later Write opens a file again.
func (w *RotatingWriter) Close() error {
	w.mu.Lock()
	defer w.mu.Unlock()
	if w.file == nil {
		return nil
	}
	err := w.file.Close()
	w.file = nil
	return err
}
