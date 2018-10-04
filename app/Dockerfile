FROM ubuntu:18.04

#
# Build a big image based on Ubuntu minimal. Use this for now as there
# are no alpine gdal/python3 packages available yet. Can always switch
# to a lighter alpine-based container later.
#

ENV TZ Europe/Amsterdam
ENV DEBIAN_FRONTEND noninteractive
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

WORKDIR /usr/local/

# Install basic dependencies
RUN apt-get update -y && \
    apt-get install -y tzdata && \
    apt-get install -y \
    wget \
    cmake \
    linux-tools-common \
    linux-tools-generic \
    software-properties-common


# Install python packages from 
RUN apt-get install -y \
    python3-matplotlib \
    python3-dev \
    python3-numpy \
    python3-pip

# Install geospatial stack from UbuntuGIS
RUN add-apt-repository -y ppa:ubuntugis/ubuntugis-unstable && \
    apt-get update -y && \
    apt-get install -y gdal-bin python3-gdal

# Copy the application directory to /opt/mapdrop
COPY . /opt/mapdrop

# Set the working directory
WORKDIR /opt/mapdrop

# Upgrade pip and install missing requirements (many have been installed already using alpine packages)
RUN cd /opt/mapdrop && \
    pip3 install -r requirements.txt

# Expose port 8080 to the Docker network
EXPOSE 8080

# Start gunicorn with application
ENTRYPOINT ["gunicorn", "mapdrop:app"]

