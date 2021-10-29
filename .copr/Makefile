.PHONY: installdeps srpm

installdeps:
	dnf -y install git make python3-devel python3-setuptools systemd

srpm: installdeps
	mkdir -p tmp.repos/SOURCES
	make dist
	rpmbuild \
		-D "_topdir tmp.repos" \
		-ts ./*.tar.gz
	cp tmp.repos/SRPMS/*.src.rpm $(outdir)
