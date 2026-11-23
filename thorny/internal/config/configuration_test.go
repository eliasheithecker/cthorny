package config

import (
	"net"
	"os"
	"path/filepath"
	"testing"
)

func writeConfig(t *testing.T, content string) *string {
	t.Helper()
	path := filepath.Join(t.TempDir(), "config.yaml")
	if err := os.WriteFile(path, []byte(content), 0o644); err != nil {
		t.Fatal(err)
	}
	return &path
}

func TestConfiguredPrimaryIPIsKept(t *testing.T) {
	cfg, err := NewConfig(writeConfig(t, "network:\n  primaryIp: '203.0.113.10'\n"))
	if err != nil {
		t.Fatal(err)
	}
	want := net.ParseIP("203.0.113.10")
	if !cfg.Network.PrimaryIP.Equal(want) {
		t.Errorf("PrimaryIP = %v, want %v", cfg.Network.PrimaryIP, want)
	}
	if !containsIP(cfg.Network.Ips, want) {
		t.Errorf("Ips %v must contain the configured PrimaryIP", cfg.Network.Ips)
	}
	if cfg.Logging.RotateMinutes != 10 {
		t.Errorf("RotateMinutes default = %d, want 10", cfg.Logging.RotateMinutes)
	}
}

func TestPrimaryIPInferredWhenUnset(t *testing.T) {
	cfg, err := NewConfig(writeConfig(t, "logging:\n  rotateMinutes: 1\n"))
	if err != nil {
		t.Fatal(err)
	}
	if want := ChoosePrimaryIP(cfg.Network.Ips); !cfg.Network.PrimaryIP.Equal(want) {
		t.Errorf("PrimaryIP = %v, want inferred %v", cfg.Network.PrimaryIP, want)
	}
	if cfg.Logging.RotateMinutes != 1 {
		t.Errorf("RotateMinutes = %d, want 1", cfg.Logging.RotateMinutes)
	}
}
