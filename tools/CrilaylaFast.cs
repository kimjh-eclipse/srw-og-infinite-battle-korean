using System;
using System.Collections.Generic;
using System.IO;

public static class CrilaylaFast
{
    static readonly int[] VLE = { 2, 3, 5, 8 };

    class BitW
    {
        public List<byte> Bytes = new List<byte>();
        int cur = 0, n = 0;
        public void Put(int value, int bits)
        {
            for (int i = bits - 1; i >= 0; i--)
            {
                cur = (cur << 1) | ((value >> i) & 1);
                n++;
                if (n == 8) { Bytes.Add((byte)cur); cur = 0; n = 0; }
            }
        }
        public byte[] Finish()
        {
            if (n != 0) { cur <<= (8 - n); Bytes.Add((byte)cur); n = 0; }
            var a = Bytes.ToArray();
            Array.Reverse(a);
            return a;
        }
    }

    static void PutCount(BitW bw, int count)
    {
        int rem = count - 3, lvl = 0;
        while (true)
        {
            int bits = lvl < 3 ? VLE[lvl] : 8;
            int cap = (1 << bits) - 1;
            if (rem < cap) { bw.Put(rem, bits); return; }
            bw.Put(cap, bits);
            rem -= cap;
            if (lvl < 3) lvl++;
        }
    }

    public static byte[] Compress(byte[] data)
    {
        int n = data.Length;
        if (n <= 0x100) throw new ArgumentException("too small");
        int m = n - 0x100;
        var body = new byte[m];
        Array.Copy(data, 0x100, body, 0, m);

        const int MAXOFF = 8189 + 3;
        const int MAXLEN = 1020;
        // hash chain over 3-byte keys; head/prev store positions (we scan pos high->low,
        // so entries already inserted are all at HIGHER positions = valid backrefs)
        int HBITS = 17, HSIZE = 1 << HBITS;
        var head = new int[HSIZE];
        for (int i = 0; i < HSIZE; i++) head[i] = -1;
        var prev = new int[m + 1];
        for (int i = 0; i <= m; i++) prev[i] = -1;

        Func<int, int> hash3 = p =>
        {
            if (p + 3 > m) return -1;
            int h = (body[p] << 16) ^ (body[p + 1] << 8) ^ body[p + 2];
            h = (h * 2654435761u.GetHashCode()) & 0x7FFFFFFF;
            return h % HSIZE;
        };

        var bw = new BitW();
        int pos = m - 1;
        while (pos >= 0)
        {
            int bestLen = 0, bestOff = 0;
            int hk = hash3(pos);
            if (hk >= 0)
            {
                int cand = head[hk];
                int tries = 0;
                while (cand >= 0 && tries < 64)
                {
                    int off = cand - pos;
                    if (off >= 3 && off <= MAXOFF)
                    {
                        int ln = 0;
                        while (ln < MAXLEN && pos - ln >= 0 && pos - ln + off < m &&
                               body[pos - ln] == body[pos - ln + off]) ln++;
                        if (ln > bestLen) { bestLen = ln; bestOff = off; if (ln >= 128) break; }
                    }
                    cand = prev[cand];
                    tries++;
                }
            }
            if (bestLen >= 3)
            {
                bw.Put(1, 1);
                bw.Put(bestOff - 3, 13);
                PutCount(bw, bestLen);
                for (int k = 0; k < bestLen; k++)
                {
                    int p = pos - k;
                    int h = hash3(p);
                    if (h >= 0) { prev[p] = head[h]; head[h] = p; }
                }
                pos -= bestLen;
            }
            else
            {
                bw.Put(0, 1);
                bw.Put(body[pos], 8);
                int h = hash3(pos);
                if (h >= 0) { prev[pos] = head[h]; head[h] = pos; }
                pos--;
            }
        }

        var stream = bw.Finish();
        var outBuf = new byte[16 + stream.Length + 0x100];
        var magic = System.Text.Encoding.ASCII.GetBytes("CRILAYLA");
        Array.Copy(magic, outBuf, 8);
        Array.Copy(BitConverter.GetBytes(m), 0, outBuf, 8, 4);
        Array.Copy(BitConverter.GetBytes(stream.Length), 0, outBuf, 12, 4);
        Array.Copy(stream, 0, outBuf, 16, stream.Length);
        Array.Copy(data, 0, outBuf, 16 + stream.Length, 0x100);
        return outBuf;
    }

    public static void CompressFile(string inPath, string outPath)
    {
        File.WriteAllBytes(outPath, Compress(File.ReadAllBytes(inPath)));
    }
}
