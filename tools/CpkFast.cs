using System;
using System.IO;

public static class CpkFast
{
    // manifest line: path \t fsize \t esize \t offsetHex
    public static void ExtractAll(string cpkPath, string manifestPath, string outDir)
    {
        var lines = File.ReadAllLines(manifestPath);
        using (var f = File.OpenRead(cpkPath))
        {
            foreach (var line in lines)
            {
                var parts = line.Split('\t');
                if (parts.Length != 4) continue;
                string path = parts[0];
                long fsize = long.Parse(parts[1]);
                long esize = long.Parse(parts[2]);
                long off = Convert.ToInt64(parts[3].Substring(2), 16);
                var blob = new byte[fsize];
                f.Seek(off, SeekOrigin.Begin);
                int read = 0;
                while (read < fsize) read += f.Read(blob, read, (int)(fsize - read));
                byte[] outData = blob;
                if (esize > fsize && fsize >= 8 && blob[0]=='C'&&blob[1]=='R'&&blob[2]=='I'&&blob[3]=='L')
                    outData = CrilaylaDecompress(blob);
                string dest = Path.Combine(outDir, path.Replace('/', Path.DirectorySeparatorChar));
                Directory.CreateDirectory(Path.GetDirectoryName(dest));
                File.WriteAllBytes(dest, outData);
            }
        }
    }

    public static byte[] CrilaylaDecompress(byte[] src)
    {
        uint usize = BitConverter.ToUInt32(src, 8);
        uint coff = BitConverter.ToUInt32(src, 12);
        var outBuf = new byte[0x100 + usize];
        Array.Copy(src, 16 + (int)coff, outBuf, 0, 0x100);
        int dpos = 16 + (int)coff - 1;
        int bitpos = 0;
        long opos = 0x100 + usize;
        Func<int,int> getbits = null;
        // use local method emulation via delegate for C# 5 compat
        getbits = (n) => {
            int v = 0;
            for (int i = 0; i < n; i++)
            {
                v <<= 1;
                v |= (src[dpos] >> (7 - bitpos)) & 1;
                bitpos++;
                if (bitpos == 8) { bitpos = 0; dpos--; }
            }
            return v;
        };
        int[] vle = new int[] {2, 3, 5, 8};
        while (opos > 0x100)
        {
            if (getbits(1) != 0)
            {
                long offset = getbits(13) + 3;
                int refc = 3;
                int lvl = 0;
                while (true)
                {
                    int bits = vle[lvl < 3 ? lvl : 3];
                    int v = getbits(bits);
                    refc += v;
                    if (v != (1 << bits) - 1) break;
                    lvl++;
                }
                for (int i = 0; i < refc; i++)
                {
                    outBuf[opos - 1] = outBuf[opos - 1 + offset];
                    opos--;
                }
            }
            else
            {
                outBuf[opos - 1] = (byte)getbits(8);
                opos--;
            }
        }
        return outBuf;
    }
}
