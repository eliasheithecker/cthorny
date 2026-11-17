"""Client-IPs den Scanner-Akteuren zuordnen und validieren."""

import logging

from utils import Context
from .t1_identify_half_open_scanners import identify_half_open_scanners
from .t2_create_zdns_ptr_input import create_zdns_ptr_input
from .t3_execute_zdns_ptr import execute_zdns_ptr
from .t4_flatten_ptr_records import flatten_ptr_records
from .t5_collect_isc_research_scanners import collect_isc_research_scanners
from .t6_join_sources import join_sources
from .t7_create_zdns_fcrdns_input import create_zdns_FCrDNS_input
from .t8_execute_zdns_fcrdns import execute_zdns_fcrdns
from .t9_validate_fcrdns import validate_fcrdns

log = logging.getLogger(__name__)

def run(ctx: Context) -> None:
    log.info(" ---- Schritt 3: Client-IPs den Scanner-Akteuren zuordnen und validieren")
    identify_half_open_scanners(ctx)
    create_zdns_ptr_input(ctx)
    execute_zdns_ptr(ctx)
    flatten_ptr_records(ctx)
    collect_isc_research_scanners(ctx)
    join_sources(ctx)
    create_zdns_FCrDNS_input(ctx)
    execute_zdns_fcrdns(ctx)
    validate_fcrdns(ctx)
    log.info(" ---- Schritt 3 abgeschlossen.")
