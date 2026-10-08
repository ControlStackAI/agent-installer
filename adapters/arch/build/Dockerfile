ARG BASE_IMAGE=archlinux@sha256:4e77cf2ea5f410e6f8be5abf93ccf17ce2436e87a138c167208356711a405dbd
FROM ${BASE_IMAGE}
ARG ARCH_SNAPSHOT
RUN printf '[options]\nArchitecture = auto\nSigLevel = Required DatabaseOptional\n[core]\nServer = https://archive.archlinux.org/repos/%s/$repo/os/$arch\n[extra]\nServer = https://archive.archlinux.org/repos/%s/$repo/os/$arch\n' "$ARCH_SNAPSHOT" "$ARCH_SNAPSHOT" > /etc/pacman.conf \
 && pacman -Syyuu --noconfirm --needed arch-install-scripts libisoburn squashfs-tools mtools dosfstools python gnupg openssl rust cargo gcc \
 && pacman -Scc --noconfirm
WORKDIR /repo
