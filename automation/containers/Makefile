CONTAINER_CMD = podman

prefix := ovirt
types := ovn-controller ovirt-provider-ovn ovirt-provider-ovn-tests

.PHONY: all $(types)

all: $(types)

$(types):
	for variant in \
		"quay.io/centos/centos:stream9 centos-stream-9-x86_64 centos-9" \
		"quay.io/centos/centos:stream10 centos-stream-10-x86_64 centos-10" \
		"quay.io/almalinuxorg/almalinux:9 rhel-9-x86_64 almalinux-9" \
		"quay.io/almalinuxorg/almalinux:10 rhel-10-x86_64 almalinux-10" \
	; do \
		set -- $$variant; \
		base_image=$$1; copr_chroot=$$2; tag=$$3; \
		cd $@; \
		$(CONTAINER_CMD) build --no-cache --rm \
			--build-arg BASE_IMAGE=$$base_image \
			--build-arg COPR_CHROOT=$$copr_chroot \
			-t $(prefix)/$@:$$tag -f Dockerfile . || exit $$?; \
		cd -; \
	done
