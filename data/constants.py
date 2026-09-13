"""
constants.py — Kafedra, Dars vaqtlari, EduPage xaritalari va boshlang'ich ma'lumotlar
"""

DAYS_UZ = ['Dushanba', 'Seshanba', 'Chorshanba', 'Payshanba', 'Juma', 'Shanba', 'Yakshanba']

DAY_Y_RANGES = [
    (400, 660, 'Dushanba'),
    (661, 920, 'Seshanba'),
    (921, 1177, 'Chorshanba'),
    (1178, 1434, 'Payshanba'),
    (1435, 1691, 'Juma'),
    (1692, 1950, 'Shanba'),
]

PERIOD_X_RANGES = [
    (172, 513, '1'),
    (514, 855, '2'),
    (856, 1197, '3'),
    (1198, 1540, '4'),
    (1541, 1882, '5'),
    (1883, 2224, '6'),
    (2225, 2566, '7'),
    (2567, 2910, '8'),
]

KAFEDRA_MAP = {
    'Jismoniy madaniyat va Sport': 'Jismoniy madaniyat va Sport',
    'Amaliy matematika-1': 'Oliy va amaliy matematika',
    'Amaliy matematika 1': 'Oliy va amaliy matematika',
    'Xorijiy til 1': 'Xorijiy tillar',
    'Xorijiy til': 'Xorijiy tillar',
    "Akademik ko'nikmalar va kasbiy kompetentlik": 'Iqtisodiyot nazariyasi',
    "O'zbekistonning eng yangi tarixi": 'Ijtimoiy fanlar',
    "O`zbekistonning eng yangi tarixi": 'Ijtimoiy fanlar',
    'Rus tili': "O'zbek va rus tillari",
    "O'zbek tili": "O'zbek va rus tillari",
    "Ma'rifat darsi": 'Ijtimoiy fanlar',
    'Mikroiqtisodiyot-2': 'Yashil iqtisodiyot',
    'Mikroiqtisodiyot': 'Yashil iqtisodiyot',
    'Iqtisodiy siyosat': 'Iqtisodiyot nazariyasi',
    'Pul va banklar': 'Bank ishi',
    'Makroiqtisodiyot': 'Makroiqtisodiyt siyosat va pragnozlashtirish',
    'Ekonometrika': 'Ekonometrika',
    "Sug'urta ishi": "Sug'urta ishi",
    'Mehnat iqtisodiyoti 2': 'Mehnat iqtisodiyoti',
    'Marketing': 'Marketing',
    'Soliq va soliqqa tortish': 'Soliq va soliqqa tortish',
    'Strategik boshqaruv': 'Innovatsion menejment',
    'Audit': 'Audit',
    'Iqtisodiy xavfsizlik': 'Iqtisodiy va moliyaviy xavfsizlik',
    'Iqtisodiy sotsiologiya': 'Ijtimoiy fanlar',
    'Korporativ boshqaruv': 'Innovatsion menejment',
    'Tarmoqlar iqtisodiyoti': 'Yashil iqtisodiyot',
    'Mehnatni muhofaza qilish': 'Mehnat iqtisodiyoti',
    "Muzokara ko'nikmalari": 'Mehnat iqtisodiyoti',
    'Ish haqi va motivatsiya': 'Mehnat iqtisodiyoti',
    'Barqaror iqtisodiy rivolanish': 'Yashil iqtisodiyot',
    'Barqaror biznes boshqaruvi': 'Yashil iqtisodiyot',
    'Barqaror rivojlanish': 'Makroiqtisodiyt siyosat va pragnozlashtirish',
    'Shaharlar iqtisodiyoti': 'Makroiqtisodiyt siyosat va pragnozlashtirish',
    'Investitsiya loyihalari tahlili': 'Makroiqtisodiyt siyosat va pragnozlashtirish',
    'Korparatsiyalarda barqaror biznes': 'Yashil iqtisodiyot',
    'Innovatsion iqtisodiyot': 'Yashil iqtisodiyot',
    'Urbanizatsiya va rivojlanish': 'Makroiqtisodiyt siyosat va pragnozlashtirish',
    "Tadqiqod usullari va ko'nikmalari": 'Makroiqtisodiyt siyosat va pragnozlashtirish',
    "Tadqiqot usullari va ko'nikmalari": 'Makroiqtisodiyt siyosat va pragnozlashtirish',
    'Dinamik makroiqtisodiyot': 'Makroiqtisodiyt siyosat va pragnozlashtirish',
    "Ta'lim marketingi": 'Iqtisodiyot nazariyasi',
    'Bilimlar iqtisodiyoti': 'Iqtisodiyot nazariyasi',
    "Psixologik maslahatlar va kouching": 'Iqtisodiyot nazariyasi',
    'Pedagogik menejment': 'Iqtisodiyot nazariyasi',
    'Pedagogik meneyjment': 'Iqtisodiyot nazariyasi',
}

HEADERS = [
    'Filtr uchun', 't/r', 'Guruh',
    "Professor-o'qituvchining F.I.Sh", 'Fan nomi', 'Kafedra',
    'Xona', 'Juft-lik', 'Talabalar soni', 'shundan, kelganlari',
    'kelmagan-lari', 'Davomat, % da',
    "Darsda yo'q talabalarning F.I.Sh.", "Mashg'ulot turi", 'Tyutor',
]

GURUH_INFO = {
    # 1-kurs
    'I-80/25': {'soni': 34, 'tyutor': 'Safarova Sevara Shokir qizi'},
    'I-81/25': {'soni': 32, 'tyutor': "Umarov Qaxramon Ruxiddin o'g'li"},
    'I-82/25': {'soni': 33, 'tyutor': "Umarov Qaxramon Ruxiddin o'g'li"},
    'I-83/25': {'soni': 34, 'tyutor': "Umarov Qaxramon Ruxiddin o'g'li"},
    'I-84/25': {'soni': 33, 'tyutor': "Umarov Qaxramon Ruxiddin o'g'li"},
    'I-85/25': {'soni': 34, 'tyutor': "Rahmonov Sadullo Shuxrat o'g'li"},
    'I-86/25': {'soni': 32, 'tyutor': "Rahmonov Sadullo Shuxrat o'g'li"},
    'I-87/25': {'soni': 32, 'tyutor': "Rahmonov Sadullo Shuxrat o'g'li"},
    'I-88/25': {'soni': 33, 'tyutor': "Rahmonov Sadullo Shuxrat o'g'li"},
    'I-89/25': {'soni': 32, 'tyutor': "Rahmonov Sadullo Shuxrat o'g'li"},
    'I-80k/25': {'soni': 34, 'tyutor': "Solijonov Sarvarjon Abdihafiz o'g'li"},
    'I-81k/25': {'soni': 33, 'tyutor': "Solijonov Sarvarjon Abdihafiz o'g'li"},
    'I-82k/25': {'soni': 33, 'tyutor': "Solijonov Sarvarjon Abdihafiz o'g'li"},
    'I-83k/25': {'soni': 32, 'tyutor': 'Safarova Sevara Shokir qizi'},
    'I-84k/25': {'soni': 33, 'tyutor': "Solijonov Sarvarjon Abdihafiz o'g'li"},
    'I-85k/25': {'soni': 33, 'tyutor': 'Safarova Sevara Shokir qizi'},
    'I-86/25i': {'soni': 25, 'tyutor': "Shamsiev Shuxrat Sayfutdin o'g'li"},
    'I-87/25i': {'soni': 26, 'tyutor': "Shamsiev Shuxrat Sayfutdin o'g'li"},
    'I-30/25': {'soni': 35, 'tyutor': "Shamsiev Shuxrat Sayfutdin o'g'li"},
    'I-31/25': {'soni': 36, 'tyutor': "Shamsiev Shuxrat Sayfutdin o'g'li"},
    'I-32/25': {'soni': 34, 'tyutor': "Shamsiev Shuxrat Sayfutdin o'g'li"},
    'I-33/25': {'soni': 35, 'tyutor': "Solijonov Sarvarjon Abdihafiz o'g'li"},
    'I-34i/25': {'soni': 31, 'tyutor': 'Safarova Sevara Shokir qizi'},
    'I-34/25i': {'soni': 31, 'tyutor': 'Safarova Sevara Shokir qizi'},
    'IRB-80/25': {'soni': 25, 'tyutor': 'Norqobilova Maftuna Soat qizi'},
    'IRB-81/25': {'soni': 24, 'tyutor': 'Norqobilova Maftuna Soat qizi'},
    'IRB-82/25': {'soni': 25, 'tyutor': 'Norqobilova Maftuna Soat qizi'},
    'IRB-83/25': {'soni': 25, 'tyutor': 'Norqobilova Maftuna Soat qizi'},
    'IRB-84/25': {'soni': 24, 'tyutor': 'Norqobilova Maftuna Soat qizi'},
    'IRB-85/25': {'soni': 22, 'tyutor': 'Norqobilova Maftuna Soat qizi'},
    'IRB-86/25i': {'soni': 31, 'tyutor': "Umarov Qaxramon Ruxiddin o'g'li"},
    'IRB-86i/25': {'soni': 31, 'tyutor': "Umarov Qaxramon Ruxiddin o'g'li"},
    # 2-kurs
    'I-01/24r':  {'soni': 0, 'tyutor': ''},
    'I-02/24r':  {'soni': 0, 'tyutor': ''},
    'I-03/24r':  {'soni': 0, 'tyutor': ''},
    'I-04/24r':  {'soni': 0, 'tyutor': ''},
    'I-50/24':   {'soni': 0, 'tyutor': ''},
    'I-51/24':   {'soni': 0, 'tyutor': ''},
    'I-52/24':   {'soni': 0, 'tyutor': ''},
    'I-53/24':   {'soni': 0, 'tyutor': ''},
    'I-54/24':   {'soni': 0, 'tyutor': ''},
    'I-55/24':   {'soni': 0, 'tyutor': ''},
    'I-56/24':   {'soni': 0, 'tyutor': ''},
    'I-57/24':   {'soni': 0, 'tyutor': ''},
    'I-58/24':   {'soni': 0, 'tyutor': ''},
    'I-59/24':   {'soni': 0, 'tyutor': ''},
    'I-50k/24':  {'soni': 0, 'tyutor': ''},
    'I-51k/24':  {'soni': 0, 'tyutor': ''},
    'I-52k/24':  {'soni': 0, 'tyutor': ''},
    'I-53k/24':  {'soni': 0, 'tyutor': ''},
    'IRB-50/24': {'soni': 0, 'tyutor': ''},
    'IRB-51/24': {'soni': 0, 'tyutor': ''},
    'IRB-52/24': {'soni': 0, 'tyutor': ''},
    'IRB-53i/24':{'soni': 0, 'tyutor': ''},
    'I-05/24i':  {'soni': 0, 'tyutor': ''},
    'I-54/24i':  {'soni': 0, 'tyutor': ''},
    'I-55/24i':  {'soni': 0, 'tyutor': ''},
}

from data.edupage_catalog import catalog_groups, COURSE_ID_RANGES

ID_TO_NAME = {group['id']: group['name'] for group in catalog_groups()}
ALL_GROUPS = list(dict.fromkeys(ID_TO_NAME.values()))

def get_kafedra(fan_nomi: str) -> str:
    for key, val in KAFEDRA_MAP.items():
        if key.lower() in fan_nomi.lower():
            return val
    return ''

def get_kurs(group_id: str) -> str:
    try:
        gid = int(group_id)
    except (TypeError, ValueError):
        return ''
    for kurs, (first, last) in COURSE_ID_RANGES.items():
        if first <= gid <= last:
            return f'{kurs}-kurs'
    return ''


def shorten_name(full_name: str) -> str:
    """RAHMONOVA GULSEVAR MAXMUD QIZI → RAHMONOVA.G.M"""
    parts = full_name.strip().split()
    if not parts:
        return full_name
    last = parts[-1].upper()
    if last in ("QIZI", "O'G'LI", "O`G`LI", "ULI", "UG'LI", "ULII"):
        parts = parts[:-1]
    if len(parts) == 1:
        return parts[0]
    familiya = parts[0]
    initials = ".".join(p[0] for p in parts[1:] if p)
    return f"{familiya}.{initials}"
