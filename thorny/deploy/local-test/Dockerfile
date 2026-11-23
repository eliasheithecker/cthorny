# Like the Ubuntu 22.04 AWS AMI: systemd as init, cron and sshd.
FROM ubuntu:22.04
RUN apt-get update \
 && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
        systemd systemd-sysv dbus cron openssh-server curl ca-certificates \
 && rm -rf /var/lib/apt/lists/*
# Docker configures the network; don't wait for systemd-networkd
RUN systemctl mask systemd-networkd-wait-online.service getty.target
STOPSIGNAL SIGRTMIN+3
CMD ["/sbin/init"]
