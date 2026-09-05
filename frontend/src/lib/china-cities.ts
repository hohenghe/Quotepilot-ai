export const CHINA_REGIONS: Record<string, string[]> = {
  '北京市': ['北京市'], '上海市': ['上海市'], '天津市': ['天津市'], '重庆市': ['重庆市'],
  '广东省': ['广州市', '深圳市', '佛山市', '东莞市', '中山市', '珠海市', '惠州市', '汕头市'],
  '浙江省': ['杭州市', '宁波市', '温州市', '台州市', '嘉兴市', '金华市'],
  '江苏省': ['南京市', '苏州市', '无锡市'], '福建省': ['厦门市', '福州市', '泉州市'],
  '山东省': ['青岛市', '济南市', '烟台市'], '河南省': ['郑州市', '洛阳市'],
  '湖北省': ['武汉市'], '湖南省': ['长沙市'], '江西省': ['南昌市'], '安徽省': ['合肥市'],
  '四川省': ['成都市', '绵阳市'], '陕西省': ['西安市'], '甘肃省': ['兰州市'],
  '青海省': ['西宁市'], '云南省': ['昆明市'], '贵州省': ['贵阳市'],
  '广西壮族自治区': ['南宁市'], '海南省': ['海口市', '三亚市'],
  '河北省': ['石家庄市', '唐山市', '保定市', '廊坊市'], '山西省': ['太原市'],
  '内蒙古自治区': ['呼和浩特市'], '辽宁省': ['沈阳市', '大连市'],
  '吉林省': ['长春市'], '黑龙江省': ['哈尔滨市'],
}

export const CHINA_PROVINCES = Object.keys(CHINA_REGIONS)

export function regionValue(province: string, city: string): string {
  return province === city ? city : `${province} ${city}`
}

export function parseRegion(value: string | null | undefined): [string, string] {
  for (const province of CHINA_PROVINCES) {
    const city = CHINA_REGIONS[province].find(item => value === item || value === regionValue(province, item))
    if (city) return [province, city]
  }
  return [CHINA_PROVINCES[0], CHINA_REGIONS[CHINA_PROVINCES[0]][0]]
}
