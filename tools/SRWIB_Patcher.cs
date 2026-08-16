// SRW OG Infinite Battle (BLJS10248) Korean patcher — RPCS3 dev_hdd0 install mode.
// Replaces the installed game-data cache SDAT and drops a translated EBOOT, avoiding
// any ISO/fSELF handling. GUI + CLI. Patch payloads live NEXT TO the exe:
//   sdat.xdelta   (original cache SDAT -> Korean SDAT, applied with xdelta.exe)
//   EBOOT.BIN     (decrypted+translated ELF, copied into USRDIR)
//   xdelta.exe    (bundled)
using System;
using System.Diagnostics;
using System.IO;
using System.Security.Cryptography;
using System.Windows.Forms;
using System.Drawing;
using System.Threading.Tasks;

static class P
{
    const string SERIAL = "BLJS10248";
    const string REL_CACHE = @"dev_hdd0\game\BLJS10248\USRDIR\cache\ps3_game_cpk.sdat";
    const string REL_EBOOT = @"dev_hdd0\game\BLJS10248\USRDIR\EBOOT.BIN";
    const string REL_SFO   = @"dev_hdd0\game\BLJS10248\PARAM.SFO";

    // known hashes
    const string SHA_SDAT_ORIG  = "551A8779C42E0A74F6E2E8ADF1B097AC12257CCA3DB8947AD77F69A0C6EE0B94";
    const string SHA_SDAT_KO    = "3856333C0A114B820E991B1193F8C42F2B4DCBFC354378353E53945AD38652AB";
    const string SHA_EBOOT_KO   = "AB1D4698BAD458835B5B4B1B420A59476FA6217FF7C5AFAF1813CA29A8F593BE";
    const long   SDAT_SIZE      = 600368256;

    static string ExeDir { get { return AppDomain.CurrentDomain.BaseDirectory; } }
    static Action<string> Log = delegate(string s) { Console.WriteLine(s); };

    static string Sha(string path)
    {
        using (var s = File.OpenRead(path))
        using (var h = SHA256.Create())
            return BitConverter.ToString(h.ComputeHash(s)).Replace("-", "");
    }

    static bool Rpcs3Running()
    {
        foreach (var p in Process.GetProcessesByName("rpcs3")) return true;
        return false;
    }

    static string CachePath(string root) { return Path.Combine(root, REL_CACHE); }
    static string EbootPath(string root) { return Path.Combine(root, REL_EBOOT); }

    static bool CheckInstall(string root)
    {
        if (!File.Exists(Path.Combine(root, "rpcs3.exe")))
            { Log("[오류] rpcs3.exe가 없습니다. RPCS3 폴더를 지정하세요."); return false; }
        if (!File.Exists(CachePath(root)))
        {
            Log("[오류] 게임 데이터가 설치되어 있지 않습니다:");
            Log("       " + CachePath(root));
            Log("       먼저 RPCS3에서 게임을 한 번 실행해 데이터를 설치하세요.");
            return false;
        }
        return true;
    }

    static void RunXdelta(string src, string patch, string outp)
    {
        var xd = Path.Combine(ExeDir, "xdelta.exe");
        if (!File.Exists(xd)) throw new FileNotFoundException("xdelta.exe가 패처 옆에 없습니다.");
        var psi = new ProcessStartInfo(xd, string.Format("-d -f -s \"{0}\" \"{1}\" \"{2}\"", src, patch, outp))
        { UseShellExecute = false, CreateNoWindow = true, RedirectStandardError = true };
        using (var pr = Process.Start(psi))
        {
            string err = pr.StandardError.ReadToEnd();
            pr.WaitForExit();
            if (pr.ExitCode != 0) throw new Exception("xdelta 적용 실패: " + err);
        }
    }

    static bool Verify(string root)
    {
        if (!CheckInstall(root)) return false;
        string c = Sha(CachePath(root));
        Log("현재 SDAT SHA: " + c);
        Log(c == SHA_SDAT_KO   ? "  -> 한국어 패치 적용됨"
          : c == SHA_SDAT_ORIG ? "  -> 원본 상태 (미패치)"
          : "  -> 알 수 없는 상태");
        if (File.Exists(EbootPath(root)))
        {
            string e = Sha(EbootPath(root));
            Log("현재 EBOOT SHA: " + e + (e == SHA_EBOOT_KO ? "  -> 한국어 EBOOT" : "  -> 원본/기타"));
        }
        else Log("EBOOT.BIN 없음 (원본 상태)");
        return true;
    }

    static bool Apply(string root)
    {
        if (Rpcs3Running()) { Log("[중단] RPCS3를 먼저 완전히 종료하세요."); return false; }
        if (!CheckInstall(root)) return false;

        string cache = CachePath(root);
        string cur = Sha(cache);
        if (cur == SHA_SDAT_KO) { Log("이미 한국어 패치가 적용되어 있습니다."); }
        else if (cur != SHA_SDAT_ORIG)
        {
            Log("[중단] 설치된 SDAT가 원본이 아닙니다(다른 패치/손상?).");
            Log("       원본 상태에서만 적용할 수 있습니다. SHA: " + cur);
            return false;
        }

        // backup NEXT TO the patcher (survives dev_hdd0/game/BLJS10248 reinstall)
        string bak = Path.Combine(ExeDir, "ps3_game_cpk.sdat.orig");
        if (!File.Exists(bak) && cur == SHA_SDAT_ORIG)
        {
            Log("원본 SDAT 백업 중 (패처 폴더에 저장)...");
            File.Copy(cache, bak, false);
        }
        var st = File.GetLastWriteTimeUtc(cache);

        if (cur == SHA_SDAT_ORIG)
        {
            Log("SDAT에 한국어 패치 적용 중 (xdelta, 시간이 걸립니다)...");
            string tmp = cache + ".tmp";
            RunXdelta(cache, Path.Combine(ExeDir, "sdat.xdelta"), tmp);
            if (new FileInfo(tmp).Length != SDAT_SIZE) { File.Delete(tmp); Log("[오류] 결과 크기 불일치"); return false; }
            string ns = Sha(tmp);
            if (ns != SHA_SDAT_KO) { File.Delete(tmp); Log("[오류] 결과 SHA 불일치: " + ns); return false; }
            try { File.SetAttributes(cache, FileAttributes.Normal); } catch { }
            File.Copy(tmp, cache, true);            // overwrite in place (avoids delete-lock)
            File.Delete(tmp);
            File.SetLastWriteTimeUtc(cache, st);   // mtime 복원 (게임 무결성 검사 대비)
            Log("SDAT 적용 완료.");
        }

        // EBOOT
        string eboot = EbootPath(root);
        string ebSrc = Path.Combine(ExeDir, "EBOOT.BIN");
        if (!File.Exists(ebSrc)) { Log("[오류] EBOOT.BIN이 패처 옆에 없습니다."); return false; }
        string ebBak = Path.Combine(ExeDir, "EBOOT.BIN.orig");
        if (File.Exists(eboot) && !File.Exists(ebBak))
            File.Copy(eboot, ebBak, false);
        var sfo = Path.Combine(root, REL_SFO);
        var eref = File.Exists(sfo) ? File.GetLastWriteTimeUtc(sfo) : st;
        File.Copy(ebSrc, eboot, true);
        File.SetLastWriteTimeUtc(eboot, eref);
        if (Sha(eboot) != SHA_EBOOT_KO) { Log("[오류] EBOOT 배치 검증 실패"); return false; }
        Log("EBOOT 배치 완료.");

        Log("");
        Log("=== 패치 완료 ===");
        Log("RPCS3에서 게임을 실행하세요. 타이틀 메뉴부터 한국어로 나옵니다.");
        return true;
    }

    static bool Restore(string root)
    {
        if (Rpcs3Running()) { Log("[중단] RPCS3를 먼저 종료하세요."); return false; }
        if (!CheckInstall(root)) return false;
        string cache = CachePath(root), bak = Path.Combine(ExeDir, "ps3_game_cpk.sdat.orig");
        if (File.Exists(bak))
        {
            var st = File.GetLastWriteTimeUtc(bak);
            try { File.SetAttributes(cache, FileAttributes.Normal); } catch { }
            File.Copy(bak, cache, true); File.SetLastWriteTimeUtc(cache, st);
            Log("SDAT 원본 복구 완료 (패처 폴더 백업 사용).");
        }
        else Log("SDAT 백업(패처 폴더의 ps3_game_cpk.sdat.orig)이 없어 건너뜁니다.");
        string eboot = EbootPath(root), ebak = Path.Combine(ExeDir, "EBOOT.BIN.orig");
        if (File.Exists(ebak)) { File.Copy(ebak, eboot, true); Log("EBOOT 원본 복구 완료."); }
        else if (File.Exists(eboot)) { File.Delete(eboot); Log("EBOOT 삭제(원본에 EBOOT 없음)."); }
        return true;
    }

    // ---------- CLI ----------
    [STAThread]
    static int Main(string[] args)
    {
        if (args.Length >= 1)
        {
            string cmd = args[0].ToLowerInvariant();
            string root = args.Length >= 2 ? args[1] : ExeDir;
            bool ok;
            try
            {
                if (cmd == "--apply") ok = Apply(root);
                else if (cmd == "--restore") ok = Restore(root);
                else if (cmd == "--verify") ok = Verify(root);
                else { Console.WriteLine("사용법: SRWIB_Patcher.exe [--apply|--restore|--verify] <RPCS3폴더>"); return 2; }
            }
            catch (Exception ex)
            {
                try { File.WriteAllText(Path.Combine(ExeDir, "patch_error.log"), ex.ToString()); } catch { }
                Console.WriteLine("ERROR: " + ex.GetType().FullName + " (자세한 내용 patch_error.log)");
                ok = false;
            }
            return ok ? 0 : 1;
        }
        Application.EnableVisualStyles();
        Application.Run(new MainForm());
        return 0;
    }

    // ---------- GUI ----------
    public class MainForm : Form
    {
        TextBox txtRoot, txtLog; CheckBox chk; Button bApply, bRestore, bVerify;
        public MainForm()
        {
            Text = "슈퍼로봇대전 OG 인피니트 배틀 한국어 패처 (RPCS3)";
            Width = 780; Height = 560; Font = new Font("맑은 고딕", 9);
            var lbl = new Label { Text = "RPCS3 폴더 (rpcs3.exe가 있는 폴더):", Left = 12, Top = 12, Width = 400 };
            txtRoot = new TextBox { Left = 12, Top = 34, Width = 640 };
            var bBrowse = new Button { Text = "찾아보기", Left = 660, Top = 33, Width = 90 };
            bBrowse.Click += (s, e) => { using (var d = new FolderBrowserDialog()) if (d.ShowDialog() == DialogResult.OK) txtRoot.Text = d.SelectedPath; };
            AllowDrop = true;
            DragEnter += (s, e) => e.Effect = DragDropEffects.Copy;
            DragDrop += (s, e) => { var f = (string[])e.Data.GetData(DataFormats.FileDrop); if (f.Length > 0) txtRoot.Text = Directory.Exists(f[0]) ? f[0] : Path.GetDirectoryName(f[0]); };

            chk = new CheckBox { Left = 12, Top = 66, Width = 740, Height = 40,
                Text = "주의: RPCS3를 완전히 종료했고, 게임을 한 번 실행해 설치했으며, 원본 백업(.orig)을 보존함을 확인합니다." };
            bVerify  = new Button { Text = "상태 검사", Left = 12,  Top = 110, Width = 150, Height = 36 };
            bApply   = new Button { Text = "한국어 패치 적용", Left = 172, Top = 110, Width = 200, Height = 36 };
            bRestore = new Button { Text = "원본으로 복구", Left = 382, Top = 110, Width = 180, Height = 36 };
            txtLog = new TextBox { Left = 12, Top = 158, Width = 740, Height = 350, Multiline = true, ReadOnly = true, ScrollBars = ScrollBars.Vertical, BackColor = Color.Black, ForeColor = Color.Lime, Font = new Font("Consolas", 9) };
            Log = s => txtLog.BeginInvoke((Action)(() => { txtLog.AppendText(s + "\r\n"); }));

            bVerify.Click += async (s, e) => await Run(() => Verify(txtRoot.Text), false);
            bApply.Click += async (s, e) => { if (!chk.Checked) { MessageBox.Show("주의사항 확인란을 체크하세요."); return; } await Run(() => Apply(txtRoot.Text), true); };
            bRestore.Click += async (s, e) => { if (!chk.Checked) { MessageBox.Show("주의사항 확인란을 체크하세요."); return; } await Run(() => Restore(txtRoot.Text), true); };

            Controls.AddRange(new Control[] { lbl, txtRoot, bBrowse, chk, bVerify, bApply, bRestore, txtLog });
        }
        async Task Run(Func<bool> act, bool guard)
        {
            bApply.Enabled = bRestore.Enabled = bVerify.Enabled = false;
            try { await Task.Run(act); } catch (Exception ex) { Log("[예외] " + ex.Message); }
            finally { bApply.Enabled = bRestore.Enabled = bVerify.Enabled = true; }
        }
    }
}
