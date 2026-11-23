package lib

import (
	"os"
	"path/filepath"
	"testing"
	"time"
)

func readFile(t *testing.T, path string) string {
	t.Helper()
	b, err := os.ReadFile(path)
	if err != nil {
		t.Fatalf("read %s: %v", path, err)
	}
	return string(b)
}

func TestRotatingWriterAlignsToIntervals(t *testing.T) {
	dir := t.TempDir()
	w, err := NewRotatingWriter(dir, "thorny-", 10*time.Minute)
	if err != nil {
		t.Fatal(err)
	}
	defer w.Close()

	// 2026-11-18 10:13:20 UTC -> window starts at 10:10:00 UTC
	now := time.Date(2026, 11, 18, 10, 13, 20, 0, time.UTC)
	w.now = func() time.Time { return now }

	if _, err := w.Write([]byte("a\n")); err != nil {
		t.Fatal(err)
	}
	now = now.Add(6*time.Minute + 39*time.Second) // 10:19:59, same window
	if _, err := w.Write([]byte("b\n")); err != nil {
		t.Fatal(err)
	}
	now = now.Add(time.Second) // 10:20:00, new window
	if _, err := w.Write([]byte("c\n")); err != nil {
		t.Fatal(err)
	}

	first := time.Date(2026, 11, 18, 10, 10, 0, 0, time.UTC).Unix()
	second := time.Date(2026, 11, 18, 10, 20, 0, 0, time.UTC).Unix()

	if got := readFile(t, w.pathFor(first)); got != "a\nb\n" {
		t.Errorf("first window: got %q", got)
	}
	if got := readFile(t, w.pathFor(second)); got != "c\n" {
		t.Errorf("second window: got %q", got)
	}
	if filepath.Base(w.pathFor(first)) != "thorny-1794996600.jsonl" {
		t.Errorf("unexpected file name %s", filepath.Base(w.pathFor(first)))
	}

	entries, _ := os.ReadDir(dir)
	if len(entries) != 2 {
		t.Errorf("expected 2 files, got %d", len(entries))
	}
}

func TestRotatingWriterAppendsAfterRestart(t *testing.T) {
	dir := t.TempDir()
	now := time.Date(2026, 11, 18, 10, 13, 20, 0, time.UTC)

	for _, line := range []string{"a\n", "b\n"} {
		w, err := NewRotatingWriter(dir, "thorny-", 10*time.Minute)
		if err != nil {
			t.Fatal(err)
		}
		w.now = func() time.Time { return now }
		if _, err := w.Write([]byte(line)); err != nil {
			t.Fatal(err)
		}
		if err := w.Close(); err != nil {
			t.Fatal(err)
		}
	}

	start := now.Unix() / 600 * 600
	w := &RotatingWriter{dir: dir, prefix: "thorny-"}
	if got := readFile(t, w.pathFor(start)); got != "a\nb\n" {
		t.Errorf("got %q", got)
	}
}

func TestRotatingWriterRejectsTinyInterval(t *testing.T) {
	if _, err := NewRotatingWriter(t.TempDir(), "x-", time.Millisecond); err == nil {
		t.Error("expected error")
	}
}
