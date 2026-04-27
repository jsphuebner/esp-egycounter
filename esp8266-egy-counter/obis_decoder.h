/*
 * obis_decoder.h - OBIS text format decoder for ESP8266
 *
 * Decodes the IEC 62056-21 text protocol used by German smart electricity
 * meters (e.g. EBZ DD3).  The telegram starts with '/' (manufacturer
 * identification line) and ends with '!'.  Each data object is identified
 * by an OBIS code in the form  A-B:C.D.E*F  followed by a value enclosed
 * in parentheses.
 *
 * Recognised OBIS codes:
 *   1-0:0.0.0   meter ID (string)
 *   0-0:1.0.0   meter ID – alternative code used by some meters
 *   1-0:1.8.0   total energy import [kWh]
 *   1-0:16.7.0  total current power [kW] → stored as W
 *   1-0:21.7.0  L1 power [kW] → stored as W
 *   1-0:41.7.0  L2 power [kW] → stored as W
 *   1-0:61.7.0  L3 power [kW] → stored as W
 *
 * Copyright (C) 2018 Johannes Huebner <dev@johanneshuebner.com>
 * SPDX-License-Identifier: GPL-3.0-or-later
 */
#pragma once
#include <Arduino.h>
#include "sml_decoder.h"   /* re-uses the CounterValues struct */

/* ======================================================================== */
/*  Internal helpers                                                         */
/* ======================================================================== */

/*
 * Search for obisCode inside telegram, then locate the next '(' and return
 * everything between that '(' and the matching ')' as a String.
 * Returns an empty String when the code is not found.
 */
static String obisExtractField(const String& telegram, const char* obisCode)
{
  int idx = telegram.indexOf(obisCode);
  if (idx < 0)
    return String();

  /* The '(' should appear within a few characters of the code end */
  int paren = telegram.indexOf('(', idx);
  if (paren < 0 || paren - idx > 12)
    return String();

  int close = telegram.indexOf(')', paren + 1);
  if (close < 0)
    return String();

  return telegram.substring(paren + 1, close);
}

/*
 * Extract a numeric value for obisCode.
 * The value string may have the form "00123.4567*kWh" – toFloat() stops at
 * the first non-numeric character so the unit suffix is ignored.
 */
static float obisExtractFloat(const String& telegram, const char* obisCode)
{
  String field = obisExtractField(telegram, obisCode);
  if (field.length() == 0)
    return 0.0f;
  return field.toFloat();
}

/* ======================================================================== */
/*  Public entry point                                                       */
/* ======================================================================== */

/*
 * decodeObis – decode a raw OBIS text telegram and populate val.
 *
 * Searches buf for the '/' start character, collects bytes up to (and
 * including) '!', then extracts the recognised OBIS data objects:
 *
 *   val.id         ← OBIS 1-0:0.0.0  (or 0-0:1.0.0)  meter ID
 *   val.etotal     ← OBIS 1-0:1.8.0  total energy import [kWh]
 *   val.ptotal     ← OBIS 1-0:16.7.0 total power [W]  (source is kW)
 *   val.pphase[0]  ← OBIS 1-0:21.7.0 L1 power [W]
 *   val.pphase[1]  ← OBIS 1-0:41.7.0 L2 power [W]
 *   val.pphase[2]  ← OBIS 1-0:61.7.0 L3 power [W]
 *
 * Returns true when a '/' start character was found and at least partial
 * data could be extracted.
 */
static bool decodeObis(const uint8_t* buf, uint16_t len, CounterValues& val)
{
  /* Locate '/' – start of the OBIS text telegram */
  uint16_t start = 0;
  while (start < len && buf[start] != '/') start++;
  if (start >= len) return false;

  /* Build a String that covers the telegram up to (and including) '!' */
  uint16_t end = start;
  while (end < len && buf[end] != '!') end++;
  if (end < len) end++; /* include the '!' */

  String telegram;
  telegram.reserve(end - start);
  telegram.concat((const char*)(buf + start), end - start);

  /* Meter ID – try primary OBIS code first, fall back to alternative */
  val.id = obisExtractField(telegram, "1-0:0.0.0");
  if (val.id.length() == 0)
    val.id = obisExtractField(telegram, "0-0:1.0.0");

  /* Total energy import in kWh */
  val.etotal = obisExtractFloat(telegram, "1-0:1.8.0");

  /* Power values: source unit is kW, stored as W */
  val.ptotal    = obisExtractFloat(telegram, "1-0:16.7.0") * 1000.0f;
  val.pphase[0] = obisExtractFloat(telegram, "1-0:21.7.0") * 1000.0f;
  val.pphase[1] = obisExtractFloat(telegram, "1-0:41.7.0") * 1000.0f;
  val.pphase[2] = obisExtractFloat(telegram, "1-0:61.7.0") * 1000.0f;

  return true;
}
