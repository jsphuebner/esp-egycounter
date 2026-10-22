/*
 * sml_decoder.h - SML (Smart Message Language) stream decoder for ESP8266
 *
 * Decodes the binary SML format used by German smart electricity meters (e.g. EBZ).
 * Extracts meter ID, total energy (kWh) and power readings (W) from an
 * SML_GetListRes message and stores them in a CounterValues struct.
 *
 * SML TL-byte encoding (per BSI TR-03109-1 / IEC 62056-46):
 *   bit 7   : more_follows (1 = second TL byte follows)
 *   bits 6:4: type  0=octet-string  5=int  6=uint  7=list
 *   bits 3:0: for type=list : number of items
 *             for other types: total field length including this TL byte
 *                              (0 and 1 are the special "null" indicators)
 *
 * Copyright (C) 2018 Johannes Huebner <dev@johanneshuebner.com>
 * SPDX-License-Identifier: GPL-3.0-or-later
 */
#pragma once
#include <Arduino.h>
#include <string.h>

/* CounterValues holds the decoded readings from a single SML telegram. */
struct CounterValues
{
  String id;       /* meter ID (hex string of server-ID bytes)     */
  float  etotal;   /* total energy import  [kWh]                   */
  float  eexport;  /* total energy export  [kWh]                   */
  float  ptotal;   /* total current power  [W]                     */
  float  pphase[3];/* per-phase power L1/L2/L3  [W]               */
};

/* ---- SML type codes (bits 6:4 of the TL byte) -------------------------- */
#define SML_TYPE_OCTET_STRING 0x00
#define SML_TYPE_INTEGER      0x05
#define SML_TYPE_UNSIGNED     0x06
#define SML_TYPE_LIST         0x07

/* ---- SML message type selectors ---------------------------------------- */
#define SML_MSG_GETLISTRES    0x0701u

/* ---- Well-known OBIS object-name codes (6 bytes each) ------------------ */
static const uint8_t OBIS_METER_ID[6]     = { 0x01, 0x00, 0x60, 0x01, 0x00, 0xFF };
static const uint8_t OBIS_ENERGY_IN[6]    = { 0x01, 0x00, 0x01, 0x08, 0x00, 0xFF };
static const uint8_t OBIS_ENERGY_OUT[6]   = { 0x01, 0x00, 0x02, 0x08, 0x00, 0xFF };
static const uint8_t OBIS_POWER_TOTAL[6]  = { 0x01, 0x00, 0x10, 0x07, 0x00, 0xFF };
static const uint8_t OBIS_POWER_L1[6]     = { 0x01, 0x00, 0x15, 0x07, 0x00, 0xFF };
static const uint8_t OBIS_POWER_L2[6]     = { 0x01, 0x00, 0x29, 0x07, 0x00, 0xFF };
static const uint8_t OBIS_POWER_L3[6]     = { 0x01, 0x00, 0x3D, 0x07, 0x00, 0xFF };

/* ---- SML framing ------------------------------------------------------- */
static const uint8_t SML_ESCAPE_SEQ[4] = { 0x1B, 0x1B, 0x1B, 0x1B };
static const uint8_t SML_START_SEQ[4]  = { 0x01, 0x01, 0x01, 0x01 };
static const uint8_t SML_END_MARKER    =   0x1A;

/* ---- CRC-16/X-25 lookup table (reflected polynomial 0x8408) ----------- */
static const uint16_t SML_CRC16_TABLE[256] = {
  0x0000, 0x1189, 0x2312, 0x329B, 0x4624, 0x57AD, 0x6536, 0x74BF,
  0x8C48, 0x9DC1, 0xAF5A, 0xBED3, 0xCA6C, 0xDBE5, 0xE97E, 0xF8F7,
  0x1081, 0x0108, 0x3393, 0x221A, 0x56A5, 0x472C, 0x75B7, 0x643E,
  0x9CC9, 0x8D40, 0xBFDB, 0xAE52, 0xDAED, 0xCB64, 0xF9FF, 0xE876,
  0x2102, 0x308B, 0x0210, 0x1399, 0x6726, 0x76AF, 0x4434, 0x55BD,
  0xAD4A, 0xBCC3, 0x8E58, 0x9FD1, 0xEB6E, 0xFAE7, 0xC87C, 0xD9F5,
  0x3183, 0x200A, 0x1291, 0x0318, 0x77A7, 0x662E, 0x54B5, 0x453C,
  0xBDCB, 0xAC42, 0x9ED9, 0x8F50, 0xFBEF, 0xEA66, 0xD8FD, 0xC974,
  0x4204, 0x538D, 0x6116, 0x709F, 0x0420, 0x15A9, 0x2732, 0x36BB,
  0xCE4C, 0xDFC5, 0xED5E, 0xFCD7, 0x8868, 0x99E1, 0xAB7A, 0xBAF3,
  0x5285, 0x430C, 0x7197, 0x601E, 0x14A1, 0x0528, 0x37B3, 0x263A,
  0xDECD, 0xCF44, 0xFDDF, 0xEC56, 0x98E9, 0x8960, 0xBBFB, 0xAA72,
  0x6306, 0x728F, 0x4014, 0x519D, 0x2522, 0x34AB, 0x0630, 0x17B9,
  0xEF4E, 0xFEC7, 0xCC5C, 0xDDD5, 0xA96A, 0xB8E3, 0x8A78, 0x9BF1,
  0x7387, 0x620E, 0x5095, 0x411C, 0x35A3, 0x242A, 0x16B1, 0x0738,
  0xFFCF, 0xEE46, 0xDCDD, 0xCD54, 0xB9EB, 0xA862, 0x9AF9, 0x8B70,
  0x8408, 0x9581, 0xA71A, 0xB693, 0xC22C, 0xD3A5, 0xE13E, 0xF0B7,
  0x0840, 0x19C9, 0x2B52, 0x3ADB, 0x4E64, 0x5FED, 0x6D76, 0x7CFF,
  0x9489, 0x8500, 0xB79B, 0xA612, 0xD2AD, 0xC324, 0xF1BF, 0xE036,
  0x18C1, 0x0948, 0x3BD3, 0x2A5A, 0x5EE5, 0x4F6C, 0x7DF7, 0x6C7E,
  0xA50A, 0xB483, 0x8618, 0x9791, 0xE32E, 0xF2A7, 0xC03C, 0xD1B5,
  0x2942, 0x38CB, 0x0A50, 0x1BD9, 0x6F66, 0x7EEF, 0x4C74, 0x5DFD,
  0xB58B, 0xA402, 0x9699, 0x8710, 0xF3AF, 0xE226, 0xD0BD, 0xC134,
  0x39C3, 0x284A, 0x1AD1, 0x0B58, 0x7FE7, 0x6E6E, 0x5CF5, 0x4D7C,
  0xC60C, 0xD785, 0xE51E, 0xF497, 0x8028, 0x91A1, 0xA33A, 0xB2B3,
  0x4A44, 0x5BCD, 0x6956, 0x78DF, 0x0C60, 0x1DE9, 0x2F72, 0x3EFB,
  0xD68D, 0xC704, 0xF59F, 0xE416, 0x90A9, 0x8120, 0xB3BB, 0xA232,
  0x5AC5, 0x4B4C, 0x79D7, 0x685E, 0x1CE1, 0x0D68, 0x3FF3, 0x2E7A,
  0xE70E, 0xF687, 0xC41C, 0xD595, 0xA12A, 0xB0A3, 0x8238, 0x93B1,
  0x6B46, 0x7ACF, 0x4854, 0x59DD, 0x2D62, 0x3CEB, 0x0E70, 0x1FF9,
  0xF78F, 0xE606, 0xD49D, 0xC514, 0xB1AB, 0xA022, 0x92B9, 0x8330,
  0x7BC7, 0x6A4E, 0x58D5, 0x495C, 0x3DE3, 0x2C6A, 0x1EF1, 0x0F78
};

/* ======================================================================== */
/*  CRC-16/X-25                                                             */
/* ======================================================================== */

/*
 * Compute CRC-16/X-25 (init=0xFFFF, poly=0x1021 reflected, xorout=0xFFFF)
 * over buf[0..len-1].  The SML end escape stores the result little-endian:
 *   buf[endPos+6] = crc & 0xFF  (low byte)
 *   buf[endPos+7] = crc >> 8    (high byte)
 */
static uint16_t smlCrc16(const uint8_t *buf, uint16_t len)
{
  uint16_t crc = 0xFFFF;
  for (uint16_t i = 0; i < len; i++)
    crc = SML_CRC16_TABLE[(buf[i] ^ crc) & 0xFF] ^ (crc >> 8);
  return crc ^ 0xFFFF;
}

/* ======================================================================== */
/*  Low-level TLV helpers                                                    */
/* ======================================================================== */

static inline uint8_t smlGetType(uint8_t tl)
{
  return (tl >> 4) & 0x07;
}

/*
 * Parse the TL byte(s) at buf[pos], advance pos past the TL, and return the
 * data length in dataLen (for list types this is the item count).
 * Returns false when there is not enough data.
 */
static bool smlParseTL(const uint8_t *buf, uint16_t bufLen, uint16_t &pos,
                       uint8_t &type, uint16_t &dataLen)
{
  if (pos >= bufLen) return false;
  uint8_t tl = buf[pos];
  type = smlGetType(tl);

  if (tl & 0x80) {
    /* Extended two-byte TL */
    if (pos + 1 >= bufLen) return false;
    uint16_t total = ((uint16_t)(tl & 0x0F) << 4) | (buf[pos + 1] & 0x0F);
    pos += 2;
    dataLen = (type == SML_TYPE_LIST) ? total : (total >= 2 ? total - 2 : 0);
  } else {
    uint16_t total = tl & 0x0F;
    pos++;
    dataLen = (type == SML_TYPE_LIST) ? total : (total >= 1 ? total - 1 : 0);
  }
  return true;
}

/*
 * Skip one complete TLV field (including any nested list items).
 * Returns false on a parse error / buffer overrun.
 */
static bool smlSkip(const uint8_t *buf, uint16_t bufLen, uint16_t &pos)
{
  if (pos >= bufLen) return false;
  uint8_t tl = buf[pos];

  /* 0x00 = end-of-message marker, 0x01 = optional-not-present (null) */
  if (tl == 0x00 || tl == 0x01) { pos++; return true; }

  uint8_t type;
  uint16_t dataLen;
  if (!smlParseTL(buf, bufLen, pos, type, dataLen)) return false;

  if (type == SML_TYPE_LIST) {
    for (uint16_t i = 0; i < dataLen; i++)
      if (!smlSkip(buf, bufLen, pos)) return false;
  } else {
    if (pos + dataLen > bufLen) return false;
    pos += dataLen;
  }
  return true;
}

/* ======================================================================== */
/*  Integer / scaler helpers                                                 */
/* ======================================================================== */

/* Parse a big-endian signed integer of up to 8 bytes. */
static int64_t smlParseInt(const uint8_t *data, uint16_t len)
{
  if (len == 0) return 0;
  int64_t v = (int8_t)data[0]; /* sign-extend the most-significant byte */
  for (uint16_t i = 1; i < len && i < 8; i++)
    v = (v << 8) | data[i];
  return v;
}

/* Parse a big-endian unsigned integer of up to 8 bytes. */
static uint64_t smlParseUint(const uint8_t *data, uint16_t len)
{
  uint64_t v = 0;
  for (uint16_t i = 0; i < len && i < 8; i++)
    v = (v << 8) | data[i];
  return v;
}

/* Multiply value by 10^scaler. */
static float smlScaled(int64_t value, int8_t scaler)
{
  float r = (float)value;
  if (scaler > 0)
    while (scaler-- > 0) r *= 10.0f;
  else
    while (scaler++ < 0) r *= 0.1f;
  return r;
}

/* ======================================================================== */
/*  SML_ListEntry parser                                                     */
/* ======================================================================== */

/*
 * Parse one SML_ListEntry (a list of 7 items) and update val when the
 * embedded OBIS code matches one of the codes we care about.
 *
 * SML_ListEntry layout:
 *   [0] objectName   – octet-string, 6 bytes (OBIS code)
 *   [1] status       – optional
 *   [2] valTime      – optional
 *   [3] unit         – optional uint8
 *   [4] scaler       – optional int8
 *   [5] value        – optional, typed
 *   [6] valueSignature – optional
 */
static void smlParseListEntry(const uint8_t *buf, uint16_t bufLen, uint16_t &pos,
                              CounterValues &val)
{
  if (pos >= bufLen) return;
  uint8_t tl = buf[pos];

  if (tl == 0x00 || tl == 0x01) { pos++; return; }
  if (smlGetType(tl) != SML_TYPE_LIST) { smlSkip(buf, bufLen, pos); return; }

  uint8_t type;
  uint16_t count;
  if (!smlParseTL(buf, bufLen, pos, type, count)) return;

  if (count < 7) {
    for (uint16_t i = 0; i < count; i++) smlSkip(buf, bufLen, pos);
    return;
  }

  /* ---- Item 0: objectName ---- */
  bool isMeterID    = false;
  bool isEnergyIn   = false;
  bool isEnergyOut  = false;
  bool isPowerTotal = false;
  bool isPowerL1    = false;
  bool isPowerL2    = false;
  bool isPowerL3    = false;
  {
    uint16_t p2 = pos;
    uint8_t  t2;
    uint16_t l2;
    if (smlParseTL(buf, bufLen, p2, t2, l2) &&
        t2 == SML_TYPE_OCTET_STRING && l2 == 6 && p2 + 6 <= bufLen)
    {
      const uint8_t *obis = buf + p2;
      if      (memcmp(obis, OBIS_METER_ID,    6) == 0) isMeterID    = true;
      else if (memcmp(obis, OBIS_ENERGY_IN,   6) == 0) isEnergyIn   = true;
      else if (memcmp(obis, OBIS_ENERGY_OUT,  6) == 0) isEnergyOut  = true;
      else if (memcmp(obis, OBIS_POWER_TOTAL, 6) == 0) isPowerTotal = true;
      else if (memcmp(obis, OBIS_POWER_L1,    6) == 0) isPowerL1    = true;
      else if (memcmp(obis, OBIS_POWER_L2,    6) == 0) isPowerL2    = true;
      else if (memcmp(obis, OBIS_POWER_L3,    6) == 0) isPowerL3    = true;
    }
  }
  smlSkip(buf, bufLen, pos); /* consume item 0 */

  bool relevant = isMeterID | isEnergyIn | isEnergyOut | isPowerTotal |
                  isPowerL1  | isPowerL2  | isPowerL3;

  if (!relevant) {
    /* Skip the remaining 6 items and any extras */
    for (uint16_t i = 1; i < count; i++) smlSkip(buf, bufLen, pos);
    return;
  }

  smlSkip(buf, bufLen, pos); /* item 1: status  */
  smlSkip(buf, bufLen, pos); /* item 2: valTime */
  smlSkip(buf, bufLen, pos); /* item 3: unit    */

  /* ---- Item 4: scaler (optional int8) ---- */
  int8_t scaler = 0;
  {
    uint8_t stl = buf[pos];
    if (stl != 0x01 && stl != 0x00) {
      uint16_t p2 = pos;
      uint8_t  t2;
      uint16_t l2;
      if (smlParseTL(buf, bufLen, p2, t2, l2) &&
          t2 == SML_TYPE_INTEGER && l2 == 1 && p2 < bufLen)
        scaler = (int8_t)buf[p2];
    }
    smlSkip(buf, bufLen, pos); /* consume item 4 */
  }

  /* ---- Item 5: value ---- */
  {
    uint8_t vtl = buf[pos];
    if (vtl != 0x01 && vtl != 0x00) {
      uint16_t p2 = pos;
      uint8_t  t2;
      uint16_t l2;
      if (smlParseTL(buf, bufLen, p2, t2, l2) && p2 + l2 <= bufLen) {

        if (isMeterID && t2 == SML_TYPE_OCTET_STRING) {
          val.id = "";
          for (uint16_t i = 0; i < l2; i++) {
            char hex[3];
            sprintf(hex, "%02X", buf[p2 + i]);
            val.id += hex;
          }
        } else if ((t2 == SML_TYPE_INTEGER || t2 == SML_TYPE_UNSIGNED) &&
                   l2 >= 1 && l2 <= 8)
        {
          int64_t raw = (t2 == SML_TYPE_INTEGER)
                        ? smlParseInt(buf + p2, l2)
                        : (int64_t)smlParseUint(buf + p2, l2);
          float   scaled = smlScaled(raw, scaler);

          if      (isEnergyIn)   val.etotal    = scaled / 1000.0f; /* Wh → kWh */
          else if (isEnergyOut)  val.eexport   = scaled / 1000.0f; /* Wh → kWh */
          else if (isPowerTotal) val.ptotal    = scaled;
          else if (isPowerL1)    val.pphase[0] = scaled;
          else if (isPowerL2)    val.pphase[1] = scaled;
          else if (isPowerL3)    val.pphase[2] = scaled;
        }
      }
    }
    smlSkip(buf, bufLen, pos); /* consume item 5 */
  }

  smlSkip(buf, bufLen, pos); /* item 6: valueSignature */

  /* Skip any extra items beyond the standard 7 */
  for (uint16_t i = 7; i < count; i++) smlSkip(buf, bufLen, pos);
}

/* ======================================================================== */
/*  SML_GetListRes parser                                                    */
/* ======================================================================== */

/*
 * Parse the body of an SML_GetListRes message (a list of 7 items):
 *   [0] clientId       – optional
 *   [1] serverId       – optional
 *   [2] listName       – optional OBIS
 *   [3] actSensorTime  – optional
 *   [4] val_list       – list of SML_ListEntry
 *   [5] listSignature  – optional
 *   [6] actGatewayTime – optional
 */
static void smlParseGetListRes(const uint8_t *buf, uint16_t bufLen, uint16_t &pos,
                               CounterValues &val)
{
  if (pos >= bufLen) return;
  if (smlGetType(buf[pos]) != SML_TYPE_LIST) { smlSkip(buf, bufLen, pos); return; }

  uint8_t  type;
  uint16_t count;
  if (!smlParseTL(buf, bufLen, pos, type, count)) return;

  if (count < 5) {
    for (uint16_t i = 0; i < count; i++) smlSkip(buf, bufLen, pos);
    return;
  }

  /* Items 0-3: clientId, serverId, listName, actSensorTime */
  smlSkip(buf, bufLen, pos);
  smlSkip(buf, bufLen, pos);
  smlSkip(buf, bufLen, pos);
  smlSkip(buf, bufLen, pos);

  /* Item 4: val_list */
  if (pos < bufLen && smlGetType(buf[pos]) == SML_TYPE_LIST) {
    uint8_t  t2;
    uint16_t listCount;
    if (smlParseTL(buf, bufLen, pos, t2, listCount)) {
      for (uint16_t i = 0; i < listCount; i++)
        smlParseListEntry(buf, bufLen, pos, val);
    }
  } else {
    smlSkip(buf, bufLen, pos);
  }

  /* Items 5 onwards */
  for (uint16_t i = 5; i < count; i++) smlSkip(buf, bufLen, pos);
}

/* ======================================================================== */
/*  Public entry point                                                       */
/* ======================================================================== */

/*
 * decodeSml – decode a raw SML byte stream and populate val.
 *
 * Looks for the SML start escape (1B1B1B1B 01010101), then walks the
 * sequence of SML_Message frames until the end escape is reached.
 * For each SML_GetListRes frame, the embedded val_list is parsed and
 * matching OBIS values are written to val:
 *
 *   val.id         ← OBIS 1.0.96.1.0.255  meter ID (hex string)
 *   val.etotal     ← OBIS 1.0.1.8.0.255   total energy import (kWh)
 *   val.eexport    ← OBIS 1.0.2.8.0.255   total energy export (kWh)
 *   val.ptotal     ← OBIS 1.0.16.7.0.255  total power (W)
 *   val.pphase[0]  ← OBIS 1.0.21.7.0.255  power L1 (W)
 *   val.pphase[1]  ← OBIS 1.0.41.7.0.255  power L2 (W)
 *   val.pphase[2]  ← OBIS 1.0.61.7.0.255  power L3 (W)
 *
 * Returns true if a valid, CRC-verified SML telegram was found and decoded.
 */
static bool decodeSml(const uint8_t *buf, uint16_t len, CounterValues &val)
{
  if (len < 16) return false;

  /* Locate start: escape sequence followed by version bytes */
  uint16_t pos = 0;
  uint16_t startPos = 0;
  bool found = false;
  while (pos + 8 <= len) {
    if (memcmp(buf + pos, SML_ESCAPE_SEQ, 4) == 0 &&
        memcmp(buf + pos + 4, SML_START_SEQ, 4) == 0)
    {
      startPos = pos;
      pos += 8;
      found = true;
      break;
    }
    pos++;
  }
  if (!found) return false;
  /* Walk SML_Message frames */
  while (pos < len) {
    /* Stop at the end escape sequence */
    if (pos + 4 <= len && memcmp(buf + pos, SML_ESCAPE_SEQ, 4) == 0) break;

    /* Skip padding/null bytes between messages */
    if (buf[pos] == 0x00) { pos++; continue; }

    /* Every SML_Message is a list */
    if (smlGetType(buf[pos]) != SML_TYPE_LIST) break;

    uint16_t msgStart = pos;
    uint8_t  type;
    uint16_t count;
    if (!smlParseTL(buf, len, pos, type, count) || count < 6) {
      pos = msgStart + 1; /* skip one byte and re-sync */
      continue;
    }

    /* Items 0-2: transactionId, groupNo, abortOnError */
    if (!smlSkip(buf, len, pos)) break;
    if (!smlSkip(buf, len, pos)) break;
    if (!smlSkip(buf, len, pos)) break;

    /* Item 3: messageBody – list(2) = [ typeSelector, body ] */
    if (pos >= len || smlGetType(buf[pos]) != SML_TYPE_LIST) {
      /* Malformed – skip remaining items and move on */
      for (uint16_t i = 3; i < count; i++) smlSkip(buf, len, pos);
      continue;
    }
    {
      uint8_t  bt;
      uint16_t bc;
      if (!smlParseTL(buf, len, pos, bt, bc) || bc < 2) {
        for (uint16_t i = 0; i < bc; i++) smlSkip(buf, len, pos);
        for (uint16_t i = 4; i < count; i++) smlSkip(buf, len, pos);
        continue;
      }

      /* Peek at the type selector (2-byte unsigned) */
      uint16_t msgType = 0;
      {
        uint16_t p2 = pos;
        uint8_t  t2;
        uint16_t l2;
        if (smlParseTL(buf, len, p2, t2, l2) && l2 == 2 && p2 + 1 < len)
          msgType = ((uint16_t)buf[p2] << 8) | buf[p2 + 1];
      }
      smlSkip(buf, len, pos); /* consume type selector */

      /* Parse or skip the message body */
      if (msgType == SML_MSG_GETLISTRES)
        smlParseGetListRes(buf, len, pos, val);
      else
        smlSkip(buf, len, pos);

      /* Skip any extra items in the messageBody list */
      for (uint16_t i = 2; i < bc; i++) smlSkip(buf, len, pos);
    }

    /* Items 4-5: CRC, endOfSmlMessage */
    if (!smlSkip(buf, len, pos)) break;
    if (!smlSkip(buf, len, pos)) break;

    /* Skip any extra items beyond the standard 6 */
    for (uint16_t i = 6; i < count; i++) smlSkip(buf, len, pos);
  }

  /* Verify end escape and check CRC
   * End escape layout: 1B1B1B1B 1A PP CRC_LO CRC_HI  (8 bytes)
   * CRC-16/X-25 covers everything from startPos up to and including PP.
   * The two CRC bytes are stored little-endian (low byte first).
   */
  if (pos + 8 > len) return false;
  if (memcmp(buf + pos, SML_ESCAPE_SEQ, 4) != 0) return false;
  if (buf[pos + 4] != SML_END_MARKER) return false;

  uint16_t crcCalc   = smlCrc16(buf + startPos, pos + 6 - startPos);
  uint16_t crcStored = (uint16_t)buf[pos + 6] | ((uint16_t)buf[pos + 7] << 8);
  if (crcCalc != crcStored) return false;

  return true;
}
