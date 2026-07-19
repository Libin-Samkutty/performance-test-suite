FROM eclipse-temurin:11-jre-alpine

ENV JMETER_VERSION=5.6.3
ENV JMETER_HOME=/opt/jmeter
ENV PATH=${JMETER_HOME}/bin:${PATH}

RUN apk add --no-cache curl tar bash python3 py3-pip && \
    curl -fsSL "https://archive.apache.org/dist/jmeter/binaries/apache-jmeter-${JMETER_VERSION}.tgz" -o /tmp/jmeter.tgz && \
    tar -xzf /tmp/jmeter.tgz -C /opt && \
    mv "/opt/apache-jmeter-${JMETER_VERSION}" "${JMETER_HOME}" && \
    rm /tmp/jmeter.tgz

# check_thresholds.py / trend_report.py are stdlib-only today; this keeps
# a stable pip-install hook available if a dependency is ever added.
COPY scripts/requirements.txt /tmp/requirements.txt
RUN pip3 install --no-cache-dir --break-system-packages -r /tmp/requirements.txt

WORKDIR /jmeter

ENTRYPOINT ["jmeter"]
