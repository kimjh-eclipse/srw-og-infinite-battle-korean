# SDAT 암호화

`ps3_game_cpk.sdat`는 PS3 NPD v4 SDAT (finalized, 비압축, FLAG_0x20 인터리브).
복호화 상수·로직은 RPCS3 `unself.cpp`/`key_vault.h`와 대조 검증했고, 재암호화는
원본을 바이트 단위로 재현하는 것으로 확인했다. 구현은 `sdat.py`.

## 헤더

```
NPD  @0x00  "NPD\0", version=4, license=0, type=0
            digest[0x10]@0x40, dev_hash[0x10]@0x60
EDAT @0x80  flags=0x0100003C, block_size=0x4000, file_size(u64)@0x88
데이터 시작 = 0x100
푸터(끝)    "SDATA 4.0.0.W\0\0\0"
```
`flags=0x0100003C` = SDAT(0x01000000) | 0x20(인터리브·메타 0x20B) | 0x10(블록키 ECB
이중) | 0x08(ENCRYPTED_KEY) | 0x04. 비압축, AES-128-CBC, 블록당 HMAC-SHA1(0x14).

## 블록 레이아웃 (FLAG_0x20 인터리브)

메타가 각 블록 앞에 붙는다.

```
block i: meta_off = 0x100 + i*(0x20 + block_size)
         data_off = meta_off + 0x20
마지막 블록 길이 = file_size % block_size, 16 정렬
```

## 키 유도 (블록마다)

```
dec_key    = dev_hash XOR SDAT_KEY
b_key      = dev_hash[:12] || BE32(i)
key_result = AES_ECB_enc(dec_key, b_key)
hash_seed  = AES_ECB_enc(dec_key, key_result)         # FLAG_0x10: ECB 2회
key_final  = AES_CBC_dec(EDAT_KEY_1, IV=0, key_result) # ERK 언랩
hash_final = AES_CBC_dec(EDAT_KEY_1, IV=0, hash_seed)[:0x10] + 0x00*4
```
- 데이터: `AES_CBC_dec(key_final, IV=npd.digest, enc)` — **IV는 전 블록 공통(digest)**,
  블록 구분은 키에서 나온다.
- 무결성: `HMAC_SHA1(hash_final, 암호문)[:0x14]`를 메타의 test hash와 비교.
  메타(0x20)는 test hash를 난수 패드로 XOR 난독화해 저장.
- version==4 → `EDAT_KEY_1`. 상수는 RPCS3 `key_vault.h` 기준.

## 헤더 CMAC (재암호화 시 필수)

RPCS3는 다음 두 CMAC을 검증한다(file_size를 바꾸면 반드시 재계산).

```
derived = AES_CBC_dec(EDAT_KEY_1, IV=0, dec_key)
0x90 = CMAC-AES(derived, 전체 메타 연접)
0xA0 = CMAC-AES(derived, header[0x00:0xA0])
```
0xB0~ 서명 영역은 RPCS3가 검사하지 않는다(fake여도 됨). 원본 파일의 두 CMAC을
위 식으로 재현 확인했다.

## 검증

- 우리 복호화 결과 == RPCS3 `--decrypt` 출력 (바이트 일치)
- `encrypt(decrypt(원본)) == 원본` (데이터 블록·크기·푸터 동일)
- 재암호화본을 다시 복호화 → 삽입한 한글 텍스트/글리프 확인

> RPCS3 `--decrypt`는 대용량에서 **프로세스 반환 후 비동기로** 결과 파일을 쓴다.
> 직후 존재 확인하면 실패로 오인하기 쉬우니 충분히 대기할 것.
