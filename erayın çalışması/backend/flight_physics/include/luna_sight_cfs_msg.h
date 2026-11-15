/**
 * @file luna_sight_cfs_msg.h
 * @brief NASA Core Flight System (cFS) & CCSDS Flight Software Interface Headers.
 *
 * LunaSight Ay Inis ve Aviyonik Yazilimi CCSDS Telemetri ve Komut Paket Tanimlari.
 * CCSDS 133.0-B-1 & NASA cFS OSAL / FSW standartlariyla tam uyumludur.
 */

#ifndef LUNA_SIGHT_CFS_MSG_H
#define LUNA_SIGHT_CFS_MSG_H

#include <stdint.h>
#include <stdbool.h>

#ifdef __cplusplus
extern "C" {
#endif

#pragma pack(push, 1)

/**
 * @brief CCSDS Birincil Paket Basligi (Primary Header - 6 Bayt)
 */
typedef struct {
    /**
     * Bayt 0-1: Stream ID (Packet Identification)
     * Bit 0-2:  Surum Numarasi (CCSDS Sürüm 1 = 000)
     * Bit 3:    Paket Tipi (0 = Telemetri, 1 = Komut)
     * Bit 4:    Ikincil Baslik Bayragi (1 = Ikincil Baslik Mevcut)
     * Bit 5-15: APID (Uygulama Sureci Kimligi - Application Process ID)
     */
    uint16_t StreamId;

    /**
     * Bayt 2-3: Dizi Kontrolu (Sequence Control)
     * Bit 0-1:  Segmentasyon Bayraklari (11 = Bolunmemis bagimsiz paket)
     * Bit 2-15: Paket Dizi Sayaci (0 - 16383 arasi artan sayac)
     */
    uint16_t Sequence;

    /**
     * Bayt 4-5: Paket Veri Uzunlugu (Packet Data Length)
     * Veri alani bayt uzunlugu - 1 (Ikincil Baslik + Payload)
     */
    uint16_t Length;
} CCSDS_PriHdr_t;

/**
 * @brief CCSDS Telemetri Ikincil Basligi (Secondary Header - Zaman Kodu)
 * CCSDS Unsegmented Time Code (UTC Saniye + Alt-saniye kesri)
 */
typedef struct {
    uint32_t Seconds;     /**< J2000 veya Gecen Gorev Zamani (MET) saniyesi */
    uint16_t Subseconds;  /**< 1/65536 saniye hassasiyetli alt zaman */
} CCSDS_TlmSecHdr_t;

/**
 * @brief CCSDS Komut Ikincil Basligi (Command Secondary Header)
 */
typedef struct {
    uint8_t  FunctionCode; /**< Komut Islev Kodu (CC - Command Code) */
    uint8_t  Checksum;     /**< Baslik ve veri butunluk kontrol toplami (XOR) */
} CCSDS_CmdSecHdr_t;

/* LunaSight cFS APID Tanimlari */
#define LUNA_SIGHT_CMD_APID         0x0180  /**< Inis Yonetimi Komut APID */
#define LUNA_SIGHT_HK_TLM_APID      0x0880  /**< Housekeeping & Ucus Durumu Telemetri APID */
#define LUNA_SIGHT_RELAY_TLM_APID   0x0881  /**< Gateway & DSN Role Telemetri APID */

/* Komut Fonksiyon Kodlari (Function Codes) */
#define LUNA_SIGHT_NOOP_CC          0x00    /**< No-Operation saglik testi */
#define LUNA_SIGHT_RESET_CC         0x01    /**< Hata ve SEU sayaclarini sifirla */
#define LUNA_SIGHT_RETARGET_CC      0x02    /**< Inis hedefini yeni koordinatlara guncelle */
#define LUNA_SIGHT_ABORT_CC         0x03    /**< Acil durum iptali (Abort to Gateway NRHO) */
#define LUNA_SIGHT_SCRUB_CC         0x04    /**< Zorunlu TMR bellek temizligi (Memory Scrub) */

/**
 * @brief LunaSight Komut Paketi (Command Packet)
 */
typedef struct {
    CCSDS_PriHdr_t    PriHdr;
    CCSDS_CmdSecHdr_t SecHdr;
    
    /* Komut Parametreleri */
    float    TargetNormX;       /**< Hedef normallestirilmis X koordinati [0.0, 1.0] */
    float    TargetNormY;       /**< Hedef normallestirilmis Y koordinati [0.0, 1.0] */
    float    TargetAltitudeM;   /**< Hedef temas raki rakimi (metre) */
    uint8_t  GuidanceMode;      /**< 0: Otomatik ML, 1: Sabit Guvenli, 2: Acil Kutusel */
    uint8_t  Spare[3];          /**< 4-bayt hizalama dolgusu */
} LunaSight_CmdPacket_t;

/**
 * @brief LunaSight Ucus Fiziği ve Housekeeping Telemetri Paketi (HK Telemetry)
 */
typedef struct {
    CCSDS_PriHdr_t    PriHdr;
    CCSDS_TlmSecHdr_t SecHdr;

    /* Ucus Durumu ve Dinamik Vektorler */
    float    AltitudeM;             /**< Ay yuzeyinden irtifa (metre) */
    float    VHorizontalMs;         /**< Yatay hiz (m/s) */
    float    VVerticalMs;           /**< Dusey alcilis hizi (m/s) */
    float    PitchDeg;              /**< Yunuslama acisi (derece) */
    float    RollDeg;               /**< Yalpalama acisi (derece) */
    float    YawDeg;                /**< Sapma acisi (derece) */
    float    FuelRemainingKg;       /**< Kalan yakit kutlesi (kg) */
    float    EngineThrustPct;       /**< Ana motor itki orani [%0 - %100] */

    /* Cevre ve Inis Tehlike Sensor Metrikleri */
    float    BoulderHazardIndex;    /**< BHI kayaç carpma tehlike indeksi (0-100) */
    float    SurfaceSlopeDeg;       /**< Yerel zemin egimi (Horn) */
    float    SurfaceRoughnessTri;   /**< TRI puruzluluk metriki (m) */
    float    SolarDiskFraction;     /**< Yari-golge gorunen Gunes orani [0.0, 1.0] */
    float    PvPowerOutputWatts;    /**< Fotovoltaik guc uretimi (Watt) */

    /* Aviyonik Saglik ve TMR Radyasyon Guvenlik Durumu */
    uint32_t SeuiCorrectionsCount;  /**< TMR onarilan SEU bit-flip sayisi */
    uint16_t CriticalFaultCount;    /**< Kurtarilamayan coklu hata sayisi */
    uint8_t  MissionPhase;          /**< 0: Yorbitten Ayrilma, 1: Frenleme, 2: Yaklasim, 3: Temas */
    uint8_t  LandingStatus;         /**< 0: NOMINAL, 1: SAFE_TOUCHDOWN, 2: ABORTED */
} LunaSight_HkPacket_t;

/**
 * @brief Artemis Gateway & NASA DSN Role ve Iletisim Telemetri Paketi
 */
typedef struct {
    CCSDS_PriHdr_t    PriHdr;
    CCSDS_TlmSecHdr_t SecHdr;

    /* Artemis Gateway (NRHO) Durumu */
    uint8_t  GatewayAosVisible;     /**< 1 = Gateway gorus hattinda (AOS), 0 = LOS */
    uint8_t  GatewayBand;           /**< 0: S-Band, 1: Ka-Band */
    float    GatewayRangeKm;        /**< Gateway mesafesi (km) */
    float    GatewayElevationDeg;   /**< Gateway yukseklik acisi (derece) */

    /* NASA DSN Istasyon ve Bicak Sirti Kirinim Marji */
    uint8_t  DsnStationId;          /**< 0: GOLDSTONE, 1: MADRID, 2: CANBERRA */
    uint8_t  DsnLinkEstablished;    /**< 1 = Baglanti acik (+3 dB marj), 0 = Kapali */
    float    DsnLinkMarginDb;       /**< DSN baglanti marji (dB) */
    float    KnifeEdgeMarginDb;     /**< Dağ arkasi acil durum kirinim marji (dB) */
    float    ObstructionAngleDeg;   /**< Daglardan oturu LoS engellenme acisi */
    uint16_t DataRateKbps;          /**< Aktif downlink veri hizi (kbps) */
    uint8_t  Spare[2];              /**< 4-bayt hizalama dolgusu */
} LunaSight_RelayTelemetry_t;

#pragma pack(pop)

#ifdef __cplusplus
}
#endif

#endif /* LUNA_SIGHT_CFS_MSG_H */
