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
static const uint8_t OBIS_METER_ID[6]    = { 0x01, 0x00, 0x60, 0x01, 0x00, 0xFF };
static const uint8_t OBIS_ENERGY_IN[6]   = { 0x01, 0x00, 0x01, 0x08, 0x00, 0xFF };
static const uint8_t OBIS_POWER_TOTAL[6] = { 0x01, 0x00, 0x10, 0x07, 0x00, 0xFF };
static const uint8_t OBIS_POWER_L1[6]    = { 0x01, 0x00, 0x15, 0x07, 0x00, 0xFF };
static const uint8_t OBIS_POWER_L2[6]    = { 0x01, 0x00, 0x29, 0x07, 0x00, 0xFF };
static const uint8_t OBIS_POWER_L3[6]    = { 0x01, 0x00, 0x3D, 0x07, 0x00, 0xFF };

/* ---- SML framing ------------------------------------------------------- */
static const uint8_t SML_ESCAPE_SEQ[4] = { 0x1B, 0x1B, 0x1B, 0x1B };
static const uint8_t SML_START_SEQ[4]  = { 0x01, 0x01, 0x01, 0x01 };

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
      else if (memcmp(obis, OBIS_POWER_TOTAL, 6) == 0) isPowerTotal = true;
      else if (memcmp(obis, OBIS_POWER_L1,    6) == 0) isPowerL1    = true;
      else if (memcmp(obis, OBIS_POWER_L2,    6) == 0) isPowerL2    = true;
      else if (memcmp(obis, OBIS_POWER_L3,    6) == 0) isPowerL3    = true;
    }
  }
  smlSkip(buf, bufLen, pos); /* consume item 0 */

  bool relevant = isMeterID | isEnergyIn | isPowerTotal |
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
 *   val.ptotal     ← OBIS 1.0.16.7.0.255  total power (W)
 *   val.pphase[0]  ← OBIS 1.0.21.7.0.255  power L1 (W)
 *   val.pphase[1]  ← OBIS 1.0.41.7.0.255  power L2 (W)
 *   val.pphase[2]  ← OBIS 1.0.61.7.0.255  power L3 (W)
 *
 * Returns true if a valid SML start sequence was found.
 */
static bool decodeSml(const uint8_t *buf, uint16_t len, CounterValues &val)
{
  if (len < 8) return false;

  /* Locate start: escape sequence followed by version bytes */
  uint16_t pos = 0;
  bool found = false;
  while (pos + 8 <= len) {
    if (memcmp(buf + pos, SML_ESCAPE_SEQ, 4) == 0 &&
        memcmp(buf + pos + 4, SML_START_SEQ, 4) == 0)
    {
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

  return true;
}
