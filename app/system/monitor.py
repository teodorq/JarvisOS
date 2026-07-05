import psutil
from datetime import datetime


class SystemMonitor:
    def get_cpu_usage(self) -> str:
        return f"{psutil.cpu_percent(interval=None):.1f}%"

    def get_ram_usage(self) -> str:
        ram = psutil.virtual_memory()
        return f"{ram.percent:.1f}%"

    def get_disk_usage(self) -> str:
        disk = psutil.disk_usage("C:\\")
        return f"{disk.percent:.1f}% zajęte"

    def get_disk_free(self) -> str:
        disk = psutil.disk_usage("C:\\")
        free_gb = disk.free / (1024 ** 3)
        total_gb = disk.total / (1024 ** 3)
        return f"{free_gb:.1f} GB wolne / {total_gb:.1f} GB"

    def get_gpu_usage(self) -> str:
        return "GPU później"

    def get_gpu_temp(self) -> str:
        return "GPU później"

    def get_vram_usage(self) -> str:
        return "GPU później"

    def get_network_speed(self) -> str:
        net = psutil.net_io_counters()
        sent_mb = net.bytes_sent / (1024 ** 2)
        recv_mb = net.bytes_recv / (1024 ** 2)
        return f"↓ {recv_mb:.0f} MB | ↑ {sent_mb:.0f} MB"

    def get_uptime(self) -> str:
        boot_time = datetime.fromtimestamp(psutil.boot_time())
        uptime = datetime.now() - boot_time

        days = uptime.days
        hours, remainder = divmod(uptime.seconds, 3600)
        minutes, seconds = divmod(remainder, 60)

        if days > 0:
            return f"{days}d {hours:02d}:{minutes:02d}:{seconds:02d}"

        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"

    def get_status_text(self) -> str:
        return (
            f"CPU: {self.get_cpu_usage()}   |   "
            f"RAM: {self.get_ram_usage()}   |   "
            f"DYSK C: {self.get_disk_usage()}   |   "
            f"CZAS PRACY: {self.get_uptime()}"
        )