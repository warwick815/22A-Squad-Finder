"""Virtual player shares stored atomically with The Black Market wallets."""
import time
SHARE_SUPPLY = 100
HOLDING_LIMIT = 20
ORDER_LIMIT = 20
from datetime import datetime, timezone


def price(points2):
    if type(points2) is not int or points2 < 0:
        raise ValueError('Invalid rating; trading paused.')
    return 100 + points2 // 20


def fee(gross):
    return 0  # Fee-free trading; historical recorded fees remain unchanged.


def available(player, now=None):
    now=time.time() if now is None else now
    try: stamp=datetime.fromisoformat(player['updated'].replace('Z','+00:00')).timestamp()
    except (ValueError,KeyError,TypeError,AttributeError):return False
    return bool(player.get('active') and not player.get('hold') and not player.get('pending')
                and player.get('baseline') is not None and 0 <= now-stamp <= 900)


class Exchange:
    def __init__(self, book):self.book=book
    @property
    def state(self):
        return self.book.data.setdefault('exchange',{'season':None,'holdings':{},'history':[], 'revision':0})
    def record(self, entry):
        s=self.state;s['revision']+=1
        s['history'].append(dict(entry,at=time.time()))
        s['history']=s['history'][-2000:]
    def supply(self, target):
        owned=sum(positions.get(str(target),{}).get('quantity',0) for positions in self.state['holdings'].values())
        return dict(cap=SHARE_SUPPLY,owned=owned,remaining=max(0,SHARE_SUPPLY-owned))
    def sync(self, season):
        s=self.state
        if s['season']==season:return
        if s['season'] is not None:
            for uid, positions in s['holdings'].items():
                cost=sum(p['cost'] for p in positions.values())
                if cost:
                    self.book.wallet(uid)
                    self.book.data['wallets'][str(uid)]+=cost
                    self.record(dict(uid=str(uid),side='season refund',quantity=sum(p['quantity'] for p in positions.values()),total=cost,name='Season '+str(s['season'])))
            s['holdings']={}
        s['season']=season;s['revision']+=1;self.book.save()
    def execute(self, uid, target, steam, name, side, quantity, unit):
        if type(quantity) is not int or not 1<=quantity<=ORDER_LIMIT:
            raise ValueError('Choose 1–20 whole shares per order.')
        if side not in ('buy','sell'):raise ValueError('Choose buy or sell.')
        if str(uid)==str(target):raise ValueError('You cannot trade your own shares.')
        s=self.state
        positions=s['holdings'].get(str(uid),{})
        p=positions.get(str(target))
        if p and p['steam']!=steam:raise ValueError('Player identity changed. Trading is paused until season settlement.')
        gross=quantity*unit
        if side=='buy':
            if quantity>self.supply(target)['remaining']:raise ValueError('Not enough shares available. Wait for another member to sell.')
            if (p or {}).get('quantity',0)+quantity>HOLDING_LIMIT:raise ValueError('Maximum 20 shares in one player.')
            if self.book.wallet(uid)<gross:raise ValueError('Not enough available betting dollars.')
            positions=s['holdings'].setdefault(str(uid),{})
            p=positions.setdefault(str(target),dict(steam=steam,name=name,quantity=0,cost=0))
            p['quantity']+=quantity;p['cost']+=gross
            self.book.data['wallets'][str(uid)]-=gross
            total=gross;charge=0;profit=None
        else:
            if not p or p['quantity']<quantity:raise ValueError('You do not own that many shares.')
            allocated=p['cost'] if quantity==p['quantity'] else p['cost']*quantity//p['quantity']
            charge=fee(gross);total=gross-charge;profit=total-allocated
            p['quantity']-=quantity;p['cost']-=allocated
            self.book.wallet(uid);self.book.data['wallets'][str(uid)]+=total
            if not p['quantity']:del positions[str(target)]
        if profit is not None:
            from market_rewards import record_profit
            record_profit(self.book, uid, profit)
        self.record(dict(uid=str(uid),target=str(target),name=name,side=side,quantity=quantity,price=unit,total=total,fee=charge,profit=profit))
        self.book.save()
        return total
