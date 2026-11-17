import re

from pyspark.sql import DataFrame
from pyspark.sql import functions as F
from pyspark.sql.window import Window

KEYWORDS = ['adscore', 'ahreds', 'alpha', 'strike', 'ampere', 'innotech' 'ant', 'lab', 'apple', 'arbor', 'observatory', 'archive', 'binaryedge',
            'bing', 'discovery', 'bitsight', 'blex', 'bot', 'caida', 'censys', 'cert', 'system', 'networks', 'cloudflare', 'cortex', 'xpanse', 'criminal',
            'cyber', 'casa', 'green', 'cymru', 'dataplane', 'domaintools', 'vulnerability', 'institute', 'errata', 'eset', 'facebook', 'google', 'census',
            'internettl', 'intrinsec', 'ipinfo', 'ipip', 'ipqualityscore', 'knoq', 'leakix', 'mail.ru', 'mpg.de', 'moz', 'dotbot', 'netsystemsresearch',
            'netcraft', 'netsystems', 'onyphe', 'openintel.nl', 'intel', 'openportstats', 'palo', 'alto', 'crawler', 'petal', 'bot', 'pnap', 'sonar',
            'project', '25499', 'quadmetrics', 'metrics', 'qualys', 'qwant', 'recyber', 'rwth', 'aachen', 'score', 'card', 'security', 'trails', 'seznam',
            'shadowserver', 'shodan', 'sogou', 'spyse', 'stanford', 'stretchoid', 'munich', 'tum.de', 'threat', 'sinkhole', 'umich', 'colorado', 'verisign',
            'withsecure', 'secure', 'yandex', 'onyphe', 'research', 'university', 'science', 'scan', 'edu', 'institute', 'muenster', 'measurement'
            ]

EXCLUDE_LIST = ['googleusercontent.com', 'googlefiber.net',
               'internettl.org', 'stretchoid', 'censys-scanner.com', 'onyphe', 'internet-census.org', 'greendottt.net', 'cabotelecom.com.br', 'binaryedge.ninja',
               'intelekt.cv.ua', 'intelnet.net.gt', 'deepfield.net', 'ipip.net', 'shodan.io', 'americandatanetworks.com', 'netsystem.net.pl',
               'cyberok.ru', 'leakix.org', 'grupoemar.mx', 'cyberresilience.io', 'mazedanetworks.net', 'flexnetworks.ca', 'enetworksgy.com',
                'rosintel.net', 'cyberinfo.net.br', 'sovintel.spb.ru', 'ib.systems', 'atmosgrbot.ru', 'host.secureserver.net', 'ded.intelignet.com.br',
               'mayacyberworld.com', 'silicanetworks.com', 'dsnetworks.net', 'cybertechnet.net.br', 'networkspeedvzla.com', 'secure-data.net',
               'testtest37.gitlab.host', 'grandenetworks.net', 'vitorianetworks.com.br', 'cyberwebatjp.inf.br', 'technetnetworks.com.br', 'sovintel',
               'mammothnetworks.com', 'promosystem.static.gvt.net.br', 'hctcnetworks.net', 'globalwifi.com.ar', 'greenlan.pl', 'braintel.net.pk',
                'panel-laboralcj.gob.mx', 'cyberspaceone.co.uk', 'gitlabrunner3.ams3.y8.net', 'postcardhorizon.org', 'enablingdimensions.com', 'artonlabs.com',
                'living-bots.net', 'gitlabrunner1.ams3.y8.net', 'internet-measurement.com', 'modat.io', 'eninetworks.com', 'oracleoutsourcing.com', 'specisk-bekes.edu.hu',
                'bufferover.run', 'gatech.edu', 'cubonetworks.net.br', 'umnyeseti.ru', 'internet-research-project.net', 'research-scanner.com', 'atomonetworks.com', 'zcomnetworks.com.pk',
                'netsystemtelecom.net.br', 'researchsrl.com.ar', 'beta.russ.green', 'tw-alpha-f.pbb.net.pk', 'academyforinternetresearch.org', 'mpg.de',
                'Cliente.HomeNet.PadreLasCasas', 'iplannetworks.net', 'www.conexionesdelosaltos.com', 'static.Cybernet', 'bras-base-altoon4123w-grc-12-65-94-154-48', 'eduara.in',
                'microscan.co.in', 'spintel.net.au', 'cabotellecom.com.br', 'bras-base-altoon4123w-grc-12-65-94-154-148', 'greenhills.net', 'b2networks.com.br',
                'klient.alfa-system.net', 'pontocertotelecom.com.br', 'cybcube.com', 'library3.uew.edu.gh', 'bot.angelmartin.name', 'ji-networks.com', 'rapid7.com', 'tor-project-exit',
                'ace-step-1.5-feishubot', 'nikhilnetworksolution.in', 'intelvision.net', 'cybernetlitoral.com.br', 'telecasa.net', 'newsysteminternet.com.br', 'alphanet.psi.br',
                'alphanet.psi.br', 'supercabotv.com.br', 'fh-muenster.de', 'arolium-educates.vpsrdns.web-hosting.com', 'lifenetworks.com.br', 'pocnroll.com', 'graphicresearch.com',
                'ngxnetworks.net', 'hjiwrite.eu.com', 'cybertelecom.net.br', 'discoverynetbd.com', 'laboratorioraly.com', 'greenet.id', 'hamdard.edu.pk', 'sitsanetworks.net', 'khi.isra.edu.pk',
                'cyberevo.net', 'dynamic.client.netsystemcampos', 'cyberinternet.net.br', 'bras-base-', 'shadowforce.io', 'upesh.edu.pk', 'giganetworks.com.br', 'gnet-itsystems.com', 'in-intercityfibernetworks.com',
                'cybervivotelecom', 'crossroaeagle.net', 'intelcom-ug.ru', 'brnetworks.com.br', 'rubinetworks.lt', 'danetworks.net', 'applefibernet.com', 'nevelesitanacsado-hbosz.edu.hu',
                'go4labs.net', 'brasilnetworks.com.br', 'nyrvsystems.com', 'crowsnestbb.net', 'tg.bots', 'deloaltobsllc.com', 'www.qualichemlab.co.in', 'neduet.edu.pk', 'green-day.mastersocialize.org.uk',
                '111.68.99.61.ciit.edu.pk', 'smtp.alphacorp.in', 'cyberdata.net.br', 'coucou-networks.fr', 'fbxo.proxad.net', 'uaf.edu.pk', 'dtuscanner.compute.dtu.dk', 'one88.cm.in.tum.de', 'reverse.alphalink.fr',
                'research-scan1.inet.haw-hamburg.de', 'greenlinepanel.top', 'gino-research.net.in.tum.de', 'hadrian.io', 'bot.cia.gov', 'moltbot.ru', 'windows2019.img-s-2vcpu-2gb-90gb-intel-nyc3-01', 'nicohubsystems.com',
                'tumndes.com', 'research-scan.cnmsb.cfd', 'host-unknown.uncsm.edu.ni', 'research.ispirt.in', 'research-scan.sysnet.ucsd.edu', 'form.securityresearch.net', 'please-see-measurements.internet-transparency.org',
                'certaincyber.net', 'dev-syd-1.sudosecuritygroup.com', 'easyname.systems', 'greendeskservers.com', 'mail.clinicasanrafael.com.co', 'intrinsec.com', 'ifxnetworks.com', 'cybertap.com.ar	', 'eds.greenlogic.pl',
                'kaspersky-labs.com', 'scalabledns.com', 'census.cubedb.io', 'benign.internet.survey.scan', 'visionheight.com', 'ports-measurements.softsec.ruhr-uni-bochum.de', 'cybertap.com.ar',
                'pub-netscan.adm.domaintools.net', 'Sq4bVLBL.strike.bz', 'office.informsystems.ru', 'research.knoq.nl', 'eudoxus.researchlytics.net', 'server.securedbserver.online', 'allcardfamily.com',
                'seranking.com', 'kurumsaltombala.com', 'mgmt.irenala.edu.mg'
               ]


def _case_insensitive_pattern(words: list[str]) -> str:
    """Baut ein case-insensitives Regex, das matcht, sobald eines der Wörter als Substring vorkommt."""
    escaped = sorted({re.escape(w.strip()) for w in words if w.strip()})
    return "(?i)(" + "|".join(escaped) + ")"


def filter_hostnames(
    sdf: DataFrame,
    hostname_col: str = "hostname",
    output_col: str = "passed_hostname_filter",
    keywords: list[str] = KEYWORDS,
    exclude_list: list[str] = EXCLUDE_LIST,
) -> DataFrame:
    """Markiert jede Zeile mit `output_col` = True, wenn der Hostname den Filter besteht.

    Ein Hostname besteht den Filter, wenn er
      - nicht leer ist,
      - mindestens ein Keyword enthält,
      - genau einmal im DataFrame vorkommt und
      - keinen Eintrag aus `exclude_list` enthält.
    Alle anderen Zeilen erhalten False. Es werden keine Zeilen entfernt.
    """
    hostname = F.col(hostname_col)
    has_hostname = hostname.isNotNull() & (F.trim(hostname) != "")
    is_unique = F.count(hostname).over(Window.partitionBy(hostname)) == 1

    passed = (
        has_hostname
        & hostname.rlike(_case_insensitive_pattern(keywords))
        & ~hostname.rlike(_case_insensitive_pattern(exclude_list))
        & is_unique
    )
    return sdf.withColumn(output_col, F.coalesce(passed, F.lit(False)))
