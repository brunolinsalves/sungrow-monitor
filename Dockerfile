ARG BUILD_FROM
FROM $BUILD_FROM
ENV LANG C.UTF-8

# Install requirements for add-on
RUN apk add --no-cache python3 py-pip
RUN apk add python3-dev
RUN apk add build-base

# Install python modules
RUN pip install config==0.4.0
RUN pip install requests==2.20.0
RUN pip install python_dateutil==2.6.1
RUN pip install pytz==2017.2
RUN pip install pymodbus==2.4.0
RUN pip install paho-mqtt==1.5.1
RUN pip install pycrypto==2.6.1

WORKDIR /data

# Copy data for add-on
COPY run.sh /
COPY config.py /
COPY modbus-sungrow.py /
COPY sungrow_monitor.py /
COPY SungrowModbusTcpClient.py /

RUN chmod a+x /run.sh

CMD [ "/run.sh" ]
