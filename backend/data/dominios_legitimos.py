"""
Lista de dominios legítimos peruanos para detección de typosquatting.
Se incluyen bancos, entidades gubernamentales y medios de comunicación.
También incluye una lista negra de dominios conocidos como peligrosos,
piratas o no confiables.
"""

DOMINIOS_LEGITIMOS = [
    # Bancos y financieras
    "bcp.com.pe",
    "viabcp.com",
    "bbva.pe",
    "interbank.pe",
    "scotiabank.com.pe",
    "bn.com.pe",               # Banco de la Nación
    "banbif.com.pe",
    "pichincha.com.pe",
    "mibanco.com.pe",
    "cmac-arequipa.com.pe",

    # Entidades del Estado
    "sunat.gob.pe",
    "reniec.gob.pe",
    "minsa.gob.pe",
    "digemid.minsa.gob.pe",
    "gob.pe",
    "pcm.gob.pe",              # Presidencia del Consejo de Ministros
    "mef.gob.pe",              # Ministerio de Economía
    "minjus.gob.pe",
    "mimp.gob.pe",
    "produce.gob.pe",
    "midis.gob.pe",
    "mtpe.gob.pe",
    "minedu.gob.pe",
    "indecopi.gob.pe",
    "sunafil.gob.pe",
    "osiptel.gob.pe",
    "osinergmin.gob.pe",
    "bcr.gob.pe",              # Banco Central de Reserva

    # Medios de comunicación
    "elcomercio.pe",
    "rpp.pe",
    "larepublica.pe",
    "andina.pe",               # Agencia Andina (oficial)
    "trome.pe",
    "peru21.pe",
    "gestion.pe",
    "correo.pe",
    "exitosa.pe",
    "panamericana.pe",

    # Otros servicios frecuentes
    "yape.com.pe",
    "plin.pe",
    "tunki.pe",
    "rappi.com",
    "ubereats.com",
    "netflix.com",
    "mercadolibre.com.pe",
    "amazon.com",
    "google.com",
    "facebook.com",
    "whatsapp.com",
]


# ---------------------------------------------------------------------------
# Lista negra de dominios no confiables
# Incluye sitios de piratería, streaming ilegal, phishing conocido,
# malware, y contenido engañoso documentado.
# ---------------------------------------------------------------------------

DOMINIOS_BLACKLIST = {
    # -----------------------------------------------------------------------
    # Streaming pirata — documentados en Latinoamérica (Infobae, El Destape 2024-2026)
    # -----------------------------------------------------------------------
    "cuevana.io",
    "cuevana2.io",
    "cuevana3.io",
    "cuevana3.me",
    "cuevana3.biz",
    "cuevana3.co",
    "cuevana3.net",
    "cuevana3.org",
    "pelisplus.to",
    "pelisplus.me",
    "pelisplus.app",
    "pelisplus.vc",
    "repelis.tv",
    "repelis24.net",
    "repelis.plus",
    "gnula.nu",
    "gnula.se",
    "gnula.ms",
    "seriesflix.to",
    "seriesflix.vip",
    "seriesflix.video",
    "cinecalidad.to",
    "cinecalidad.mx",
    "cinecalidad.ac",
    "peliculasyonkis.com",
    "mejortorrent.com",
    "elitetorrent.net",
    "zonatorrent.tv",
    "torrentlocura.com",
    "mhdtvworld.com",
    # IPTV piratas bloqueadas en Latinoamérica 2026 (El Mostrador, FayerWayer 2026)
    "magis.tv",
    "magistv.app",
    "magistv.co",
    "xupermovil.com",
    "xupertvapp.com",
    "flujotv.com",
    "flujotv.net",
    # Otros streaming piratas populares en Perú
    "miramovie.net",
    "miramovie.com",
    "pelicula24.com",
    "peliculasid.com",
    "verpeliculas24.com",
    "verpeliculasonline.nu",
    "doramasyt.com",
    "animesuma.com",
    "animeflv.net",
    "animeflv.io",
    "animelatino.nu",
    "mundoanime.tv",

    # -----------------------------------------------------------------------
    # Phishing documentado en Perú — BCP (WeLiveSecurity 2023, Group-IB 2024)
    # -----------------------------------------------------------------------
    "bcpzonasegura.com",
    "bcpzonasegura.net",
    "bcp-verificacion.com",
    "bcp-credito.com",
    "bcp-prestamo.com",
    "bcp-dineroalinstante.com",
    "bcpprestamo.com",
    "bcpbanco.net",
    "bcpdigital.net",
    "creditobcp.com",
    # BBVA
    "bbva-alertas.com",
    "bbva-seguro.com",
    "bbva-peru.net",
    "bbvaperu.net",
    "bbva-verificacion.com",
    "bbva-prestamo.com",
    # Interbank
    "interbank-alerta.com",
    "interbank-seguro.com",
    "interbankperu.net",
    "interbank-credito.com",
    # Scotiabank
    "scotiabank-peru.net",
    "scotiabank-alerta.com",
    # Banco de la Nación (Infobae Perú 2026)
    "bancodelanacion-peru.com",
    "bn-peru.net",
    "banconacion.net",
    # SUNAT
    "sunat-consulta.com",
    "sunat-ruc.net",
    "sunat-afp.com",
    "sunat-devolucion.com",
    "sunat-peru.net",
    "sunat-factura.com",
    # RENIEC
    "reniec-consulta.com",
    "reniec-dni.com",
    "reniec-peru.net",
    # Yape / Plin
    "yape-bono.com",
    "yape-ganador.com",
    "yapeperu.net",
    "yapegana.com",
    "yapepremio.com",
    "plin-peru.com",
    "plin-bono.com",
    # ONP / AFP (estafas previsionales)
    "onp-consulta.com",
    "onp-retiro.com",
    "afp-retiro.com",
    "retiro-afp.com",
    # SUNARP / MTC / otros gubernamentales
    "sunarp-consulta.com",
    "mtc-licencia.com",
    "mtc-peru.net",
    "essalud-cita.com",
    "essalud-peru.net",

    # -----------------------------------------------------------------------
    # Préstamos y esquemas Ponzi / inversiones fraudulentas en Perú
    # -----------------------------------------------------------------------
    "dinero-rapido-peru.com",
    "prestamo-facil-peru.com",
    "creditoexpress-peru.com",
    "inversiones-garantizadas.com",
    "ganadinero-peru.com",
    "trabajodesdecasa-peru.com",

    # -----------------------------------------------------------------------
    # Noticias falsas / desinformación documentada
    # -----------------------------------------------------------------------
    "eldebate.com.mx",
    "lasnoticiasdehoy.com",
    "infobae-noticias.com",
    "noticiasperu24.net",
    "alertaperu.net",
    "diariocorrecto.com",
    "noticiastotales.net",
    "periodicodelpueblo.com",
    "verdadperu.com",
    "notiperú.net",

    # -----------------------------------------------------------------------
    # Malware / adware / bundleware documentado
    # -----------------------------------------------------------------------
    "softonic.com",
    "brothersoft.com",
    "filehippo.com",
    "freeware.com",
    "downloadastro.com",
    "opencandy.com",
    "conduit.com",
    "delta-homes.com",
    "babylon.com",

    # -----------------------------------------------------------------------
    # Casinos / apuestas no reguladas en Perú (Mincetur no las autoriza)
    # -----------------------------------------------------------------------
    "1xbet.com",
    "1xbet.pe",
    "22bet.com",
    "megapari.com",
    "betwinner.com",
    "betwinner.pe",
    "mostbet.com",
    "melbet.com",
    "melbet.pe",
    "linebet.com",
    "888starz.bet",
    "pin-up.casino",
    "rabona.com",
    "leon.bet",
}

# Razones asociadas a cada dominio de la lista negra
# Si un dominio no tiene razón específica, se usa la genérica
BLACKLIST_REASONS = {
    # Streaming pirata
    "cuevana.io":       "Sitio de streaming pirata — distribuye contenido sin licencia",
    "cuevana2.io":      "Sitio de streaming pirata — distribuye contenido sin licencia",
    "cuevana3.io":      "Sitio de streaming pirata — distribuye contenido sin licencia",
    "cuevana3.me":      "Sitio de streaming pirata — distribuye contenido sin licencia",
    "cuevana3.biz":     "Sitio de streaming pirata — distribuye contenido sin licencia",
    "cuevana3.co":      "Sitio de streaming pirata — distribuye contenido sin licencia",
    "cuevana3.net":     "Sitio de streaming pirata — distribuye contenido sin licencia",
    "cuevana3.org":     "Sitio de streaming pirata — distribuye contenido sin licencia",
    "pelisplus.to":     "Sitio de streaming pirata — distribuye contenido sin licencia",
    "pelisplus.me":     "Sitio de streaming pirata — distribuye contenido sin licencia",
    "pelisplus.app":    "Sitio de streaming pirata — distribuye contenido sin licencia",
    "pelisplus.vc":     "Sitio de streaming pirata — distribuye contenido sin licencia",
    "repelis.tv":       "Sitio de streaming pirata — distribuye contenido sin licencia",
    "repelis24.net":    "Sitio de streaming pirata — distribuye contenido sin licencia",
    "gnula.nu":         "Sitio de streaming pirata — distribuye contenido sin licencia",
    "seriesflix.to":    "Sitio de streaming pirata — distribuye contenido sin licencia",
    "cinecalidad.to":   "Sitio de streaming pirata — distribuye contenido sin licencia",
    "cinecalidad.mx":   "Sitio de streaming pirata — distribuye contenido sin licencia",
    "magis.tv":         "Plataforma IPTV pirata — bloqueada judicialmente en Latinoamérica en 2026",
    "magistv.app":      "Plataforma IPTV pirata — bloqueada judicialmente en Latinoamérica en 2026",
    "magistv.co":       "Plataforma IPTV pirata — bloqueada judicialmente en Latinoamérica en 2026",
    "xupermovil.com":   "Plataforma IPTV pirata (XuperTV) — bloqueada judicialmente en 2026",
    "xupertvapp.com":   "Plataforma IPTV pirata (XuperTV) — bloqueada judicialmente en 2026",
    "flujotv.com":      "Plataforma IPTV pirata — operador detenido en Ecuador en 2024",
    "flujotv.net":      "Plataforma IPTV pirata — operador detenido en Ecuador en 2024",
    "animeflv.net":     "Sitio de anime pirata — distribuye contenido sin licencia",
    "animeflv.io":      "Sitio de anime pirata — distribuye contenido sin licencia",
    # Phishing BCP (WeLiveSecurity 2023, Group-IB 2024)
    "bcpzonasegura.com":        "Sitio de phishing — suplanta al BCP para robar credenciales bancarias",
    "bcpzonasegura.net":        "Sitio de phishing — suplanta al BCP para robar credenciales bancarias",
    "bcp-verificacion.com":     "Sitio de phishing — suplanta al BCP para robar credenciales bancarias",
    "bcp-credito.com":          "Sitio de phishing — suplanta al BCP con falsas ofertas de crédito",
    "bcp-prestamo.com":         "Sitio de phishing — suplanta al BCP con falsas ofertas de préstamo",
    "bcp-dineroalinstante.com": "Sitio de phishing — explota la marca 'Dinero al Instante' del BCP",
    "bcpprestamo.com":          "Sitio de phishing — suplanta al BCP para robar datos",
    # Phishing BBVA
    "bbva-alertas.com":         "Sitio de phishing — suplanta al BBVA para robar credenciales bancarias",
    "bbva-seguro.com":          "Sitio de phishing — suplanta al BBVA para robar credenciales bancarias",
    "bbva-verificacion.com":    "Sitio de phishing — suplanta al BBVA para robar credenciales bancarias",
    "bbva-prestamo.com":        "Sitio de phishing — suplanta al BBVA con falsas ofertas de préstamo",
    # Phishing Interbank
    "interbank-alerta.com":     "Sitio de phishing — suplanta a Interbank para robar credenciales",
    "interbank-seguro.com":     "Sitio de phishing — suplanta a Interbank para robar credenciales",
    # Phishing Estado peruano
    "sunat-consulta.com":       "Sitio de phishing — suplanta a SUNAT para robar datos tributarios",
    "sunat-ruc.net":            "Sitio de phishing — suplanta a SUNAT para robar datos tributarios",
    "sunat-devolucion.com":     "Sitio de phishing — suplanta a SUNAT con falsas devoluciones de impuestos",
    "reniec-consulta.com":      "Sitio de phishing — suplanta a RENIEC para robar datos de identidad",
    "reniec-dni.com":           "Sitio de phishing — suplanta a RENIEC para robar datos de identidad",
    "essalud-cita.com":         "Sitio de phishing — suplanta a EsSalud para robar datos personales",
    # Phishing Yape / Plin
    "yape-bono.com":            "Sitio de phishing — suplanta a Yape con falsas promociones y bonos",
    "yape-ganador.com":         "Sitio de phishing — suplanta a Yape con falsas promociones",
    "yapeperu.net":             "Sitio de phishing — suplanta a Yape para robar credenciales",
    "yapegana.com":             "Sitio de phishing — suplanta a Yape con falsas promociones",
    "plin-bono.com":            "Sitio de phishing — suplanta a Plin con falsas promociones",
    # Phishing AFP / ONP
    "onp-retiro.com":           "Sitio de phishing — suplanta a la ONP para robar datos previsionales",
    "afp-retiro.com":           "Sitio de phishing — suplanta a AFP con falsas opciones de retiro",
    "retiro-afp.com":           "Sitio de phishing — suplanta a AFP con falsas opciones de retiro",
    # Phishing Banco de la Nación (Infobae Perú 2026)
    "bancodelanacion-peru.com": "Sitio de phishing — suplanta al Banco de la Nación",
    # Préstamos / esquemas fraudulentos
    "dinero-rapido-peru.com":       "Sitio de estafa — ofrece préstamos falsos para robar datos",
    "prestamo-facil-peru.com":      "Sitio de estafa — ofrece préstamos falsos para robar datos",
    "inversiones-garantizadas.com": "Posible esquema Ponzi — promete rendimientos garantizados irreales",
    "ganadinero-peru.com":          "Sitio de estafa — promete ganancias fáciles para captar víctimas",
    # Malware / adware
    "softonic.com":     "Distribuye software con adware y bundleware — instala programas no deseados",
    "filehippo.com":    "Distribuye software con bundleware — instala programas no deseados",
    "conduit.com":      "Adware conocido — secuestra el navegador y redirige búsquedas",
    "babylon.com":      "Adware conocido — secuestra el navegador y redirige búsquedas",
    # Casinos no regulados en Perú
    "1xbet.com":        "Casa de apuestas no regulada en Perú por el Mincetur",
    "1xbet.pe":         "Casa de apuestas no regulada en Perú por el Mincetur",
    "22bet.com":        "Casa de apuestas no regulada en Perú por el Mincetur",
    "megapari.com":     "Casa de apuestas no regulada en Perú por el Mincetur",
    "betwinner.com":    "Casa de apuestas no regulada en Perú por el Mincetur",
    "betwinner.pe":     "Casa de apuestas no regulada en Perú por el Mincetur",
    "mostbet.com":      "Casa de apuestas no regulada en Perú por el Mincetur",
    "melbet.com":       "Casa de apuestas no regulada en Perú por el Mincetur",
    "melbet.pe":        "Casa de apuestas no regulada en Perú por el Mincetur",
    "linebet.com":      "Casa de apuestas no regulada en Perú por el Mincetur",
}

BLACKLIST_DEFAULT_REASON = "Dominio identificado como no confiable, peligroso o con contenido ilegal"
