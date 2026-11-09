import json, time, urllib3, random, asyncio
from protobuf_decoder.protobuf_decoder import Parser
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

Key, Iv = bytes([89, 103, 38, 116, 99, 37, 68, 69, 117, 104, 54, 37, 90, 99, 94, 56]), bytes([54, 111, 121, 90, 68, 114, 50, 50, 69, 51, 121, 99, 104, 106, 77, 37])


async def EnC_PacKeT(HeX, K, V):
    return AES.new(K, AES.MODE_CBC, V).encrypt(pad(bytes.fromhex(HeX), 16)).hex()


async def EnC_Uid(H, Tp):
    e, H = [], int(H)
    while H:
        e.append((H & 0x7F) | (0x80 if H > 0x7F else 0))
        H >>= 7
    return bytes(e).hex() if Tp == 'Uid' else None


async def EnC_Vr(N):
    if N < 0:
        return b""
    H = []
    while True:
        BesTo = N & 0x7F
        N >>= 7
        if N:
            BesTo |= 0x80
        H.append(BesTo)
        if not N:
            break
    return bytes(H)


async def CrEaTe_VarianT(field_number, value):
    field_header = (field_number << 3) | 0
    return await EnC_Vr(field_header) + await EnC_Vr(value)


async def CrEaTe_LenGTh(field_number, value):
    field_header = (field_number << 3) | 2
    encoded_value = value.encode() if isinstance(value, str) else value
    return await EnC_Vr(field_header) + await EnC_Vr(len(encoded_value)) + encoded_value


async def CrEaTe_ProTo(fields):
    packet = bytearray()
    for field, value in fields.items():
        if isinstance(value, dict):
            nested_packet = await CrEaTe_ProTo(value)
            packet.extend(await CrEaTe_LenGTh(field, nested_packet))
        elif isinstance(value, int):
            packet.extend(await CrEaTe_VarianT(field, value))
        elif isinstance(value, str) or isinstance(value, bytes):
            packet.extend(await CrEaTe_LenGTh(field, value))
    return packet


async def DecodE_HeX(H):
    R = hex(H)
    F = str(R)[2:]
    if len(F) == 1:
        F = "0" + F
        return F
    return F


async def Fix_PackEt(parsed_results):
    result_dict = {}
    for result in parsed_results:
        field_data = {}
        field_data['wire_type'] = result.wire_type
        if result.wire_type in ("varint", "string", "bytes"):
            field_data['data'] = result.data
        elif result.wire_type == 'length_delimited':
            field_data["data"] = await Fix_PackEt(result.data.results)
        result_dict[result.field] = field_data
    return result_dict


async def DeCode_PackEt(input_text):
    try:
        parsed_results = Parser().parse(input_text)
        parsed_results_dict = await Fix_PackEt(parsed_results)
        return json.dumps(parsed_results_dict)
    except Exception as e:
        print(f"error {e}")
        return None


def xMsGFixinG(n):
    return '🗿'.join(str(n)[i:i + 3] for i in range(0, len(str(n)), 3))


async def xBunnEr():
    bN = [902000306, 902000305, 902000003, 902000016, 902000017, 902000019, 902031010, 902043025, 902043024, 902000020, 902000021, 902000023, 902000070, 902000087, 902000108, 902000011, 902049020, 902049018, 902049017, 902049016, 902049015, 902049003, 902033016, 902033017, 902033018, 902048018, 902000306, 902000305, 902000079]
    return random.choice(bN)


async def GeneRaTePk(Pk, N, K, V):
    PkEnc = await EnC_PacKeT(Pk, K, V)
    _ = await DecodE_HeX(int(len(PkEnc) // 2))
    if len(_) == 2:
        HeadEr = N + "000000"
    elif len(_) == 3:
        HeadEr = N + "00000"
    elif len(_) == 4:
        HeadEr = N + "0000"
    elif len(_) == 5:
        HeadEr = N + "000"
    else:
        print('ErroR => GeneRatinG ThE PacKeT !! ')
    return bytes.fromhex(HeadEr + _ + PkEnc)


async def Send_GhosTs(Uid, Nm, sQ, K, V):
    fields = {1: 61, 2: {1: int(Uid), 2: {1: int(Uid), 2: 1159, 3: f'{Nm}', 5: 12, 6: 9999999, 7: 1, 8: {2: 1, 3: 1}, 9: 3}, 3: sQ}}
    return await GeneRaTePk((await CrEaTe_ProTo(fields)).hex(), '0515', K, V)


async def ExiT(idT, K, V):
    fields = {1: 7, 2: {1: idT}}
    return await GeneRaTePk((await CrEaTe_ProTo(fields)).hex(), '0515', K, V)


async def send_sticker_squad(Msg, Tp2, id, K, V):
    try:
        sticker_packs = [("1200000002", 1, 13)]
        pack_id, start, end = random.choice(sticker_packs)
        sticker_no = random.randint(start, end)
        sticker_json = f'{{"StickerStr":"[1={pack_id}-{sticker_no}]","type":"Sticker"}}'
        fields = {
            1: id, 2: Tp2, 3: 0, 4: Msg, 5: 801050514, 7: 0, 8: sticker_json,
            9: {
                1: '@zuyxx_2', 2: await xBunnEr(), 4: 330, 8: '@zuyxx_2f',
                10: 1, 12: 1, 13: {1: 2},
                14: {1: 12484827014, 2: 8, 3: "\u0010\u0015\b\n\u000b\u0013\f\u000f\u0011\u0004\u0007\u0002\u0003\r\u000e\u0012\u0001\u0005\u0006"}
            },
            10: 'en', 13: {2: 1, 3: 1}, 14: {},
        }
        Pk = (await CrEaTe_ProTo(fields)).hex()
        Pk = "080112" + await EnC_Uid(len(Pk) // 2, Tp='Uid') + Pk
        return await GeneRaTePk(Pk, '1201', K, V)
    except Exception as e:
        print(f"Error send_sticker_squad: {e}")
        return None


async def send_sticker_clan(Msg, Tp2, id, K, V):
    try:
        sticker_packs = [("1200000002", 1, 13)]
        pack_id, start, end = random.choice(sticker_packs)
        sticker_no = random.randint(start, end)
        sticker_json = f'{{"StickerStr":"[1={pack_id}-{sticker_no}]","type":"Sticker"}}'
        fields = {
            1: id, 2: Tp2, 3: 1, 4: Msg, 5: 801050514, 7: 0, 8: sticker_json,
            9: {
                1: '@zuyxx_2', 2: await xBunnEr(), 4: 330, 8: '@zuyxx_2f',
                10: 1, 12: 1, 13: {1: 2},
                14: {1: 12484827014, 2: 8, 3: "\u0010\u0015\b\n\u000b\u0013\f\u000f\u0011\u0004\u0007\u0002\u0003\r\u000e\u0012\u0001\u0005\u0006"}
            },
            10: 'en', 13: {2: 1, 3: 1}, 14: {},
        }
        Pk = (await CrEaTe_ProTo(fields)).hex()
        Pk = "080112" + await EnC_Uid(len(Pk) // 2, Tp='Uid') + Pk
        return await GeneRaTePk(Pk, '1201', K, V)
    except Exception as e:
        print(f"Error send_sticker_clan: {e}")
        return None


async def send_sticker_private(Msg, Tp2, id, K, V):
    try:
        sticker_packs = [("1200000002", 1, 13)]
        pack_id, start, end = random.choice(sticker_packs)
        sticker_no = random.randint(start, end)
        sticker_json = f'{{"StickerStr":"[1={pack_id}-{sticker_no}]","type":"Sticker"}}'
        fields = {
            1: id, 2: Tp2, 3: 2, 4: Msg, 5: 801050514, 7: 0, 8: sticker_json,
            9: {
                1: '@zuyxx_2', 2: await xBunnEr(), 4: 330, 8: '@zuyxx_2f',
                10: 1, 12: 1, 13: {1: 2},
                14: {1: 12484827014, 2: 8, 3: "\u0010\u0015\b\n\u000b\u0013\f\u000f\u0011\u0004\u0007\u0002\u0003\r\u000e\u0012\u0001\u0005\u0006"}
            },
            10: 'en', 13: {2: 1, 3: 1}, 14: {},
        }
        Pk = (await CrEaTe_ProTo(fields)).hex()
        Pk = "080112" + await EnC_Uid(len(Pk) // 2, Tp='Uid') + Pk
        return await GeneRaTePk(Pk, '1201', K, V)
    except Exception as e:
        print(f"Error send_sticker_private: {e}")
        return None


async def send_chat_inTeam(Msg, Tp, Tp2, id, K, V):
    fields = {
        1: id, 2: Tp2, 3: 0, 4: Msg, 5: 801050514, 7: 0,
        9: {
            1: '@zuyxx_2', 2: await xBunnEr(), 4: 330, 8: '@zuyxx_2f',
            10: 1, 12: 1, 13: {1: 2},
            14: {1: 12484827014, 2: 8, 3: "\u0010\u0015\b\n\u000b\u0013\f\u000f\u0011\u0004\u0007\u0002\u0003\r\u000e\u0012\u0001\u0005\u0006"}
        },
        10: 'en', 13: {2: 1, 3: 1}, 14: {},
    }
    Pk = (await CrEaTe_ProTo(fields)).hex()
    Pk = "080112" + await EnC_Uid(len(Pk) // 2, Tp='Uid') + Pk
    return await GeneRaTePk(Pk, '1201', K, V)


async def xSEndMsgClan(Msg, Tp, Tp2, id, K, V):
    fields = {
        1: id, 2: Tp2, 3: 1, 4: Msg, 5: 801050514, 7: 0,
        9: {
            1: '@zuyxx_2', 2: await xBunnEr(), 4: 330, 8: '@zuyxx_2f',
            10: 1, 12: 1, 13: {1: 2},
            14: {1: 12484827014, 2: 8, 3: "\u0010\u0015\b\n\u000b\u0013\f\u000f\u0011\u0004\u0007\u0002\u0003\r\u000e\u0012\u0001\u0005\u0006"}
        },
        10: 'en', 13: {2: 1, 3: 1}, 14: {},
    }
    Pk = (await CrEaTe_ProTo(fields)).hex()
    Pk = "080112" + await EnC_Uid(len(Pk) // 2, Tp='Uid') + Pk
    return await GeneRaTePk(Pk, '1201', K, V)


async def xSEndMsg(Msg, Tp, Tp2, id, K, V):
    fields = {
        1: id, 2: Tp2, 3: 2, 4: Msg, 5: 801050514, 7: 0,
        9: {
            1: '@zuyxx_2', 2: await xBunnEr(), 4: 330, 8: '@zuyxx_2f',
            10: 1, 12: 1, 13: {1: 2},
            14: {1: 12484827014, 2: 8, 3: "\u0010\u0015\b\n\u000b\u0013\f\u000f\u0011\u0004\u0007\u0002\u0003\r\u000e\u0012\u0001\u0005\u0006"}
        },
        10: 'en', 13: {2: 1, 3: 1}, 14: {},
    }
    Pk = (await CrEaTe_ProTo(fields)).hex()
    Pk = "080112" + await EnC_Uid(len(Pk) // 2, Tp='Uid') + Pk
    return await GeneRaTePk(Pk, '1201', K, V)