using System;
using System.Collections.Generic;
using System.Net.Http;
using System.Text;
using System.Threading.Tasks;
using System.Web.Script.Serialization;

namespace Easycode.CaptureOverlay
{
    internal sealed class CaptureApiClient : IDisposable
    {
        private readonly HttpClient _http;
        private readonly JavaScriptSerializer _serializer = new JavaScriptSerializer { MaxJsonLength = 32 * 1024 * 1024 };

        internal CaptureApiClient(string origin)
        {
            if (String.IsNullOrWhiteSpace(origin) || (!origin.StartsWith("http://") && !origin.StartsWith("https://")))
                throw new ArgumentException("IDE 服务地址无效");
            _http = new HttpClient();
            _http.BaseAddress = new Uri(origin.TrimEnd('/') + "/");
            _http.Timeout = TimeSpan.FromSeconds(50);
        }

        internal async Task<Dictionary<string, object>> PostAsync(string path, Dictionary<string, object> payload)
        {
            string json = _serializer.Serialize(payload ?? new Dictionary<string, object>());
            HttpResponseMessage response = await _http.PostAsync(path.TrimStart('/'),
                new StringContent(json, Encoding.UTF8, "application/json"));
            string body = await response.Content.ReadAsStringAsync();
            Dictionary<string, object> data = null;
            try { data = _serializer.DeserializeObject(body) as Dictionary<string, object>; }
            catch { }
            if (!response.IsSuccessStatusCode)
            {
                string detail = data == null ? body : JsonUtil.String(data, "detail", body);
                throw new InvalidOperationException(String.IsNullOrWhiteSpace(detail) ? "后端请求失败" : detail);
            }
            return data ?? new Dictionary<string, object>();
        }

        internal async Task<Dictionary<string, object>> GetAsync(string path)
        {
            HttpResponseMessage response = await _http.GetAsync(path.TrimStart('/'));
            string body = await response.Content.ReadAsStringAsync();
            Dictionary<string, object> data = null;
            try { data = _serializer.DeserializeObject(body) as Dictionary<string, object>; }
            catch { }
            if (!response.IsSuccessStatusCode)
            {
                string detail = data == null ? body : JsonUtil.String(data, "detail", body);
                throw new InvalidOperationException(String.IsNullOrWhiteSpace(detail) ? "后端请求失败" : detail);
            }
            return data ?? new Dictionary<string, object>();
        }

        public void Dispose()
        {
            _http.Dispose();
        }
    }
}
