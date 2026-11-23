package config

import (
	"log/slog"
	"net"
	"os"

	"github.com/juriroemer/thorny/internal/filter"
	"github.com/juriroemer/thorny/internal/handler"
	"go.yaml.in/yaml/v4"
)

// Configuration struct, holds config file configuration
type Config struct {
	C2 net.IP `yaml:"c2"`

	Network struct {
		Ips []net.IP
		// PrimaryIP can be set in the config (e.g. the public IP of a cloud VM,
		// which is NATed and not visible on the interface). If unset, it is
		// inferred from the default interface.
		PrimaryIP   net.IP `yaml:"primaryIp"`
		Iface       string `yaml:"iface"`
		Promiscuous bool   `yaml:"promiscuous"`
	}

	Logging struct {
		Snaplen           int    `yaml:"snaplen"`
		Packetsperlogfile int    `yaml:"packetsperlogfile"`
		LogDir            string `yaml:"logDir"`
		// RotateMinutes: a new log file is started at every full interval (UTC). Default 10.
		RotateMinutes int `yaml:"rotateMinutes"`
	}

	Snort struct {
		Rules string `yaml:"rules"`
	}

	Filters []filter.CfgFilter `yaml:"filters"`

	Handlers handler.Handlers `yaml:"handlers"`

	Tls map[any]any `yaml:"tls"`
}

// NewConfig constructs a new config struct, infers network interface and IP
func NewConfig(configPath *string) (*Config, error) {
	config := &Config{}

	file, err := os.Open(*configPath)
	if err != nil {
		return nil, err
	}

	defer file.Close()

	decoder := yaml.NewDecoder(file)

	if err := decoder.Decode(&config); err != nil {
		return nil, err
	}

	iface := InferDefaultNInterface()
	if iface != nil {
		addrs, err := iface.Addrs()
		if err != nil {
			slog.Warn("failed to get addresses for interface", "iface", iface.Name, "err", err)
		} else {
			ips := ExtractIPs(addrs)
			filtered := FilterSensorIPs(ips)
			config.Network.Ips = filtered
		}
	} else {
		slog.Warn("no default network interface inferred; Network.Ips will be empty")
	}

	// A configured PrimaryIP wins over the inferred one. It is also added to
	// Network.Ips, since that list ends up in the TLS certificate.
	if config.Network.PrimaryIP == nil {
		config.Network.PrimaryIP = ChoosePrimaryIP(config.Network.Ips)
	} else if !containsIP(config.Network.Ips, config.Network.PrimaryIP) {
		config.Network.Ips = append([]net.IP{config.Network.PrimaryIP}, config.Network.Ips...)
	}

	if config.Logging.RotateMinutes <= 0 {
		config.Logging.RotateMinutes = 10
	}

	// config defaults; the new yaml fork yaml/go-yaml does not seem to have default values yet :(
	if config.Network.Iface == "" && iface != nil {
		config.Network.Iface = iface.Name
	}

	return config, nil
}

func containsIP(ips []net.IP, ip net.IP) bool {
	for _, i := range ips {
		if i.Equal(ip) {
			return true
		}
	}
	return false
}
