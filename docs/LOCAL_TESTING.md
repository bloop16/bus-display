# Local Testing (ohne SD Card Flashing!)

## Option 1: Docker ARM Emulation (FASTEST!)

```bash
# Enable ARM emulation (once)
docker run --rm --privileged multiarch/qemu-user-static --reset -p yes

# Create Dockerfile
cat > Dockerfile << 'EOF'
FROM arm32v7/python:3.11-slim
RUN apt-get update && apt-get install -y python3-pil python3-flask python3-requests python3-bs4
WORKDIR /app
COPY . .
EXPOSE 5000
CMD ["python3", "main.py", "--mock-display"]
EOF

# Build + Run
docker build -t bus-display .
docker run -p 5000:5000 bus-display
```

Visit: http://localhost:5000

## Option 2: QEMU Full Pi Emulation

Full Pi emulation - slower but accurate.

```bash
# Install QEMU
sudo apt install qemu-system-arm

# Download kernel
wget https://github.com/dhruvvyas90/qemu-rpi-kernel/raw/master/kernel-qemu-5.10.63-bullseye
wget https://github.com/dhruvvyas90/qemu-rpi-kernel/raw/master/versatile-pb-bullseye-5.10.63.dtb

# Boot Pi OS image
qemu-system-arm -M versatilepb -cpu arm1176 -m 256 \
  -kernel kernel-qemu-5.10.63-bullseye \
  -dtb versatile-pb-bullseye-5.10.63.dtb \
  -hda raspios.img \
  -append "root=/dev/sda2 panic=1 rootfstype=ext4 rw" \
  -net nic -net user,hostfwd=tcp::5022-:22,hostfwd=tcp::5000-:5000 \
  -no-reboot -nographic
```

SSH: `ssh pi@localhost -p 5022`

## Option 3: Dev Server (Current)

Test on 192.168.0.99 with mock display - works great!

## Recommended Workflow

1. **Dev:** Docker ARM (fast iteration)
2. **Test:** QEMU (full integration)
3. **Validate:** Real Pi Zero (final check)
