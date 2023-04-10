FROM python:3.7-slim-bullseye

WORKDIR /vpcplus-ibm-be
COPY requirements.txt /vpcplus-ibm-be/requirements.txt

# Install pre-requisites
RUN apt-get update && apt-get install -y \
    build-essential \
    default-libmysqlclient-dev \
    iputils-ping \
    python3-dev # This installs 3.9 .. look into this.

# Set the C_FORCE_ROOT environment variable for the Celery process, replace later
ENV C_FORCE_ROOT true
# this is not recomended, look into this

# after grpcio version 1.30, the default poling strategy changed to epollex which doesnt support fork.
# these envs will enable grpc latest version to work with fork
# https://github.com/grpc/grpc/blob/353eb9aab267181096d12dc9b3a91089ac4e264e/doc/fork_support.md for details
ENV GRPC_POLL_STRATEGY epoll1

ADD . /vpcplus-ibm-be

RUN pip3 install --upgrade pip \
    && pip3 install -r requirements.txt
