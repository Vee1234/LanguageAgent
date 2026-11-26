# The sandbox the factory's verify job runs a PR's code in (docs/factory.md, "A trusted copy
# decides the merge"). The build context is the PR's checkout; this file is always master's copy.
# Installing runs here, inside the image build: the PR's install scripts never run on the runner,
# and the judge (master's scripts/ticket_analysis.py) only reads each command's exit code from
# `docker run --rm --network none`.
FROM node:20-bookworm@sha256:8f693eaa7e0a8e71560c9a82b55fd54c2ae920a2ba5d2cde28bac7d1c01c9ba5
RUN apt-get update \
 && apt-get install -y --no-install-recommends python3-pytest python3-dotenv \
 && rm -rf /var/lib/apt/lists/*
COPY . /w
WORKDIR /w
RUN npm --prefix app ci
